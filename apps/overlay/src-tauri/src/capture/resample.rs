//! resample.rs — einfacher linearer Resampler + Mono-Downmix (kein Anti-Aliasing-Filter).
//!
//! Bewusst simpel gehalten: lineare Interpolation zwischen benachbarten Samples, kein
//! Polyphase-/Sinc-Filter. Für Sprach-STT bei Zielrate 16 kHz ausreichend (Voxtral verarbeitet
//! bereits komprimierte/telefonietaugliche Sprache), aber **kein** Broadcast-Qualitäts-
//! Resampler — das ist eine bewusste, dokumentierte Einschränkung, kein verstecktes Detail.

pub struct LinearResampler {
    input_rate: u32,
    output_rate: u32,
    channels: usize,
    /// Position im Eingangs-Sample-Raster (fraktional, in Eingangs-Samples).
    phase: f64,
    last_mono: f32,
    have_last: bool,
}

impl LinearResampler {
    pub fn new(input_rate: u32, output_rate: u32, channels: usize) -> Self {
        Self {
            input_rate,
            output_rate,
            channels: channels.max(1),
            phase: 0.0,
            last_mono: 0.0,
            have_last: false,
        }
    }

    /// Nimmt einen interleaved Multi-Channel-`f32`-Block entgegen (cpal-Rohformat), mischt auf
    /// Mono und resampled auf `output_rate`; gibt fertige `i16`-PCM-Samples zurück.
    pub fn push_f32(&mut self, interleaved: &[f32]) -> Vec<i16> {
        let frames = interleaved.len() / self.channels;
        if frames == 0 {
            return Vec::new();
        }
        let mut mono = Vec::with_capacity(frames);
        for f in 0..frames {
            let mut sum = 0.0f32;
            for c in 0..self.channels {
                sum += interleaved[f * self.channels + c];
            }
            mono.push(sum / self.channels as f32);
        }

        if self.input_rate == self.output_rate {
            self.have_last = true;
            self.last_mono = *mono.last().expect("frames > 0 geprüft");
            return mono.iter().map(|s| to_i16(*s)).collect();
        }

        let ratio = self.input_rate as f64 / self.output_rate as f64;
        let mut out = Vec::new();
        let prev = if self.have_last { self.last_mono } else { mono[0] };
        // Virtuelle erweiterte Quelle [prev, mono...]; `phase` zählt Position darin.
        let extended_last_index = mono.len(); // Index von `prev` ist 0, mono[i] liegt bei i+1
        while self.phase < extended_last_index as f64 {
            let idx = self.phase.floor() as usize;
            let frac = (self.phase - idx as f64) as f32;
            let s0 = if idx == 0 { prev } else { mono[idx - 1] };
            let s1 = if idx < mono.len() { mono[idx] } else { *mono.last().expect("frames > 0") };
            out.push(to_i16(s0 + (s1 - s0) * frac));
            self.phase += ratio;
        }
        self.phase -= extended_last_index as f64;
        self.have_last = true;
        self.last_mono = *mono.last().expect("frames > 0 geprüft");
        out
    }
}

fn to_i16(sample: f32) -> i16 {
    (sample.clamp(-1.0, 1.0) * i16::MAX as f32) as i16
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn passthrough_when_rates_match() {
        let mut r = LinearResampler::new(16_000, 16_000, 1);
        let out = r.push_f32(&[0.5, -0.5, 0.0]);
        assert_eq!(out.len(), 3);
    }

    #[test]
    fn downsamples_and_downmixes() {
        // 2 Kanäle @ 48kHz -> Mono @ 16kHz: 3 Eingangs-Frames sollten ~1 Ausgangs-Sample ergeben.
        let mut r = LinearResampler::new(48_000, 16_000, 2);
        let input = [0.1, 0.1, 0.2, 0.2, 0.3, 0.3];
        let out = r.push_f32(&input);
        assert!(out.len() <= 2);
    }
}
