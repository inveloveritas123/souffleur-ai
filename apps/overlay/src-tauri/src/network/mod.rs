//! network — WebSocket-Client gegen das Backend (`/ws/v1/live`, Welle-14-Vertrag).
//!
//! **EU-Routing (Gate E1):** Dieser Client verbindet sich AUSSCHLIESSLICH mit der vom Nutzer
//! konfigurierten Backend-Basis-URL (Default `ws://localhost:8000`, siehe
//! `src/lib/config.ts` im Frontend) — niemals direkt mit Mistral oder einem anderen Non-EU-
//! Endpunkt. Das Overlay kennt keinen Mistral-API-Key; Secrets bleiben ausschließlich im
//! Backend (kein Secret im Overlay-Code, siehe Task-Vorgabe).
//!
//! Ablauf (spiegelt `apps/backend/src/souffleur/api/live.py`):
//! 1. `connect_async` zur Backend-URL.
//! 2. Erste Nachricht: JSON-Text `{"type":"start", tenant_id, session_id, consent_ref,
//!    sample_rate, language}`.
//! 3. Danach laufend binäre Frames: interleaved Stereo-PCM s16le (Kanal 0 = Coach/Mikrofon,
//!    Kanal 1 = Gegenüber/System-Audio) — siehe `mix_and_send`.
//! 4. Eingehende JSON-Text-Nachrichten (`transcript.*`/`trigger.fired`/`card.*`/`error`/
//!    `session.*`) werden 1:1 als Tauri-Event ans Frontend weitergereicht (kein Parsen/
//!    Interpretieren hier — die Anzeige-Logik lebt im Frontend, siehe `src/lib/bus-events.ts`).

use futures_util::stream::SplitSink;
use futures_util::{SinkExt, StreamExt};
use serde::Serialize;
use serde_json::Value;
use tauri::{AppHandle, Emitter};
use tokio::net::TcpStream;
use tokio::sync::{mpsc, oneshot};
use tokio_tungstenite::tungstenite::Message;
use tokio_tungstenite::{MaybeTlsStream, WebSocketStream};

use crate::capture::CHUNK_SAMPLES;

/// Tauri-Event-Name für weitergereichte Bus-Events (siehe `src/lib/bus-events.ts`).
pub const BUS_EVENT: &str = "souffleur://bus-event";
/// Tauri-Event-Name für Transport-/Verbindungsfehler (kein Bus-Event, kommt vom WS selbst).
pub const SESSION_ERROR_EVENT: &str = "souffleur://session-error";
/// Tauri-Event-Name für Statuswechsel der Verbindung ("closed").
pub const SESSION_STATUS_EVENT: &str = "souffleur://session-status";

type WsSink = SplitSink<WebSocketStream<MaybeTlsStream<TcpStream>>, Message>;

#[derive(Serialize)]
struct StartMessage<'a> {
    #[serde(rename = "type")]
    kind: &'static str,
    tenant_id: &'a str,
    session_id: &'a str,
    consent_ref: &'a str,
    sample_rate: u32,
    language: Option<&'a str>,
}

pub struct StartSessionArgs {
    pub ws_url: String,
    pub tenant_id: String,
    pub session_id: String,
    pub consent_ref: String,
    pub sample_rate: u32,
    pub language: Option<String>,
}

/// Handle auf eine laufende Session — `stop()` beendet Sende- und Empfangs-Task.
pub struct SessionHandle {
    stop_tx: oneshot::Sender<()>,
}

impl SessionHandle {
    pub fn stop(self) {
        let _ = self.stop_tx.send(());
    }
}

/// Baut die WS-Verbindung auf, sendet den Start-Handshake und startet Mixer- + Empfangs-Task.
pub async fn start_session(
    app: AppHandle,
    args: StartSessionArgs,
    coach_rx: mpsc::Receiver<Vec<i16>>,
    counterpart_rx: mpsc::Receiver<Vec<i16>>,
) -> Result<SessionHandle, String> {
    let (ws_stream, _response) = tokio_tungstenite::connect_async(&args.ws_url)
        .await
        .map_err(|e| format!("WebSocket-Verbindung zu {} fehlgeschlagen: {e}", args.ws_url))?;
    let (mut write, read) = ws_stream.split();

    let start_msg = StartMessage {
        kind: "start",
        tenant_id: &args.tenant_id,
        session_id: &args.session_id,
        consent_ref: &args.consent_ref,
        sample_rate: args.sample_rate,
        language: args.language.as_deref(),
    };
    let start_json = serde_json::to_string(&start_msg).map_err(|e| e.to_string())?;
    write
        .send(Message::Text(start_json.into()))
        .await
        .map_err(|e| format!("Start-Handshake fehlgeschlagen: {e}"))?;

    let (stop_tx, stop_rx) = oneshot::channel::<()>();

    // Mixer-Task: mischt Coach(Kanal0)/Counterpart(Kanal1) zu interleaved Stereo-PCM und
    // sendet Binär-Frames. Eigener Task, damit ein langsamer Read die Sende-Seite nicht blockt.
    tokio::spawn(mix_and_send(coach_rx, counterpart_rx, write));

    // Empfangs-Task: JSON-Bus-Events 1:1 an das Frontend weiterreichen.
    tokio::spawn(receive_loop(app, read, stop_rx));

    Ok(SessionHandle { stop_tx })
}

async fn receive_loop(
    app: AppHandle,
    mut read: futures_util::stream::SplitStream<WebSocketStream<MaybeTlsStream<TcpStream>>>,
    mut stop_rx: oneshot::Receiver<()>,
) {
    loop {
        tokio::select! {
            _ = &mut stop_rx => break,
            msg = read.next() => {
                match msg {
                    Some(Ok(Message::Text(text))) => forward_event(&app, text.as_str()),
                    Some(Ok(Message::Close(_))) | None => {
                        let _ = app.emit(SESSION_STATUS_EVENT, "closed");
                        break;
                    }
                    Some(Err(err)) => {
                        let _ = app.emit(SESSION_ERROR_EVENT, err.to_string());
                        break;
                    }
                    _ => {}
                }
            }
        }
    }
}

fn forward_event(app: &AppHandle, text: &str) {
    match serde_json::from_str::<Value>(text) {
        Ok(value) => {
            let _ = app.emit(BUS_EVENT, value);
        }
        Err(_) => {
            // Kein Klartext-Log des Rohinhalts (Gate E2) — nur, dass Parsing fehlschlug.
            let _ = app.emit(SESSION_ERROR_EVENT, "Ungültiges Event-Format vom Backend empfangen");
        }
    }
}

async fn mix_and_send(mut coach_rx: mpsc::Receiver<Vec<i16>>, mut counterpart_rx: mpsc::Receiver<Vec<i16>>, mut write: WsSink) {
    use std::collections::VecDeque;
    let mut coach_buf: VecDeque<i16> = VecDeque::new();
    let mut counterpart_buf: VecDeque<i16> = VecDeque::new();
    let mut interval = tokio::time::interval(std::time::Duration::from_millis(20));

    loop {
        tokio::select! {
            chunk = coach_rx.recv() => {
                match chunk {
                    Some(c) => coach_buf.extend(c),
                    None => break,
                }
            }
            chunk = counterpart_rx.recv() => {
                match chunk {
                    Some(c) => counterpart_buf.extend(c),
                    None => break,
                }
            }
            _ = interval.tick() => {
                let frame = drain_interleaved(&mut coach_buf, &mut counterpart_buf, CHUNK_SAMPLES);
                if write.send(Message::Binary(frame.into())).await.is_err() {
                    break;
                }
            }
        }
    }
    let _ = write.close().await;
}

/// Holt je `n` Samples aus beiden Puffern (Null-Padding bei Unterlauf) und interleaved sie zu
/// Stereo-PCM-s16le-Bytes (Kanal 0 = Coach, Kanal 1 = Counterpart) — exakt das Format, das der
/// Backend-Live-Vertrag für `SessionContext.channels == 2` erwartet.
fn drain_interleaved(
    coach: &mut std::collections::VecDeque<i16>,
    counterpart: &mut std::collections::VecDeque<i16>,
    n: usize,
) -> Vec<u8> {
    let mut bytes = Vec::with_capacity(n * 2 * 2);
    for _ in 0..n {
        let c = coach.pop_front().unwrap_or(0);
        let p = counterpart.pop_front().unwrap_or(0);
        bytes.extend_from_slice(&c.to_le_bytes());
        bytes.extend_from_slice(&p.to_le_bytes());
    }
    bytes
}
