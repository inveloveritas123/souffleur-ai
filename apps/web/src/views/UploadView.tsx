import { useCallback, useRef, useState, type ChangeEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ApiClientError, uploadAudioForProtocol } from "../api/client";
import { useConsent } from "../state/ConsentContext";
import { useProtocol } from "../state/ProtocolContext";

type RecordingState = "idle" | "recording" | "recorded";

/**
 * Schritt 2: Audio einer beendeten Aufnahme hochladen ODER direkt im Browser
 * aufnehmen (Mikrofon). Diese View ist nur über RequireConsent erreichbar —
 * Einwilligung (Schritt 1) liegt also bereits vor.
 */
export function UploadView() {
  const { consent } = useConsent();
  const { setProtocol } = useProtocol();
  const navigate = useNavigate();

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [recordedBlob, setRecordedBlob] = useState<Blob | null>(null);
  const [recordingState, setRecordingState] = useState<RecordingState>("idle");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordedChunksRef = useRef<Blob[]>([]);

  const audioToSubmit = selectedFile ?? recordedBlob;

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    setSelectedFile(file);
    if (file) {
      setRecordedBlob(null);
      setRecordingState("idle");
    }
  }

  const startRecording = useCallback(async () => {
    setError(null);
    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      setError("Mikrofon-Aufnahme wird in dieser Umgebung nicht unterstützt. Bitte Datei hochladen.");
      return;
    }
    try {
      // Bessere STT-Qualität: Mono + Rauschunterdrückung/AGC, höhere Aufnahme-Bitrate.
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      const recorder = new MediaRecorder(stream, { audioBitsPerSecond: 128000 });
      recordedChunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) recordedChunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        const blob = new Blob(recordedChunksRef.current, { type: "audio/webm" });
        setRecordedBlob(blob);
        setSelectedFile(null);
        setRecordingState("recorded");
        stream.getTracks().forEach((track) => track.stop());
      };
      mediaRecorderRef.current = recorder;
      recorder.start();
      setRecordingState("recording");
    } catch {
      setError("Zugriff auf das Mikrofon wurde verweigert oder ist nicht möglich.");
    }
  }, []);

  const stopRecording = useCallback(() => {
    mediaRecorderRef.current?.stop();
  }, []);

  async function handleSubmit() {
    if (!consent || !audioToSubmit) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const protocol = await uploadAudioForProtocol(audioToSubmit, consent.consentRef);
      setProtocol(protocol);
      navigate("/protocol");
    } catch (cause) {
      const message =
        cause instanceof ApiClientError
          ? cause.message
          : "Upload fehlgeschlagen. Bitte erneut versuchen.";
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section data-testid="upload-view" aria-labelledby="upload-heading">
      <h1 id="upload-heading">Audio hochladen oder aufnehmen</h1>
      <p>Einwilligung liegt vor ({consent?.consentRef}). Lade eine beendete Aufnahme hoch oder nimm sie direkt auf.</p>

      <div className="upload-section">
        <label htmlFor="upload-file-input">Audiodatei auswählen</label>
        <input
          id="upload-file-input"
          data-testid="upload-file-input"
          type="file"
          accept="audio/*"
          onChange={handleFileChange}
        />
      </div>

      <div className="upload-section">
        <p>oder direkt aufnehmen:</p>
        {recordingState !== "recording" ? (
          <button type="button" data-testid="upload-record-start-button" onClick={startRecording}>
            Aufnahme starten
          </button>
        ) : (
          <button type="button" data-testid="upload-record-stop-button" onClick={stopRecording}>
            Aufnahme beenden
          </button>
        )}
        {recordingState === "recorded" ? (
          <span data-testid="upload-record-status">Aufnahme bereit zum Hochladen.</span>
        ) : null}
      </div>

      <button
        type="button"
        data-testid="upload-submit-button"
        disabled={!audioToSubmit || isSubmitting}
        onClick={handleSubmit}
      >
        {isSubmitting ? "Wird verarbeitet …" : "Hochladen und Protokoll erzeugen"}
      </button>

      {error ? (
        <p role="alert" data-testid="upload-error">
          {error}
        </p>
      ) : null}
    </section>
  );
}
