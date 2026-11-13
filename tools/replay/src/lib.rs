//! Narrow offline Caretaker replay core. It does not acquire from or write to
//! hardware. CAN support is intentionally limited to unsigned little-endian
//! signals; unsupported DBC geometry is rejected, never guessed.

mod io;
pub mod json;

use io::{interpolate, read_csv, reference_source, references, required, timestamp_seconds, Reference};
use json::Json;
use std::fs;
use std::path::{Path, PathBuf};

#[derive(Clone, Debug)]
pub struct Decoder {
    pub message_id: u32,
    pub message_name: String,
    pub signal_name: String,
    pub start_bit: u8,
    pub length: u8,
    pub scale: f64,
    pub offset: f64,
    pub minimum: f64,
    pub maximum: f64,
    pub unit: String,
}

impl Decoder {
    pub fn from_dbc(path: &Path, signal: &str) -> Result<Self, String> {
        let text = fs::read_to_string(path).map_err(|e| format!("{}: {e}", path.display()))?;
        let mut message: Option<(u32, String, usize)> = None;
        for line in text.lines() {
            let line = line.trim();
            if let Some(rest) = line.strip_prefix("BO_ ") {
                let mut parts = rest.split_whitespace();
                let id = parts.next().ok_or("BO_ lacks id")?.parse::<u32>().map_err(|_| "invalid DBC message id")?;
                let name = parts.next().ok_or("BO_ lacks name")?.trim_end_matches(':').to_string();
                let length = parts.next().ok_or("BO_ lacks length")?.parse::<usize>().map_err(|_| "invalid DBC byte length")?;
                if length > 8 { return Err("classic CAN replay supports at most 8 data bytes".into()); }
                message = Some((id, name, length));
            } else if let Some(rest) = line.strip_prefix("SG_ ") {
                let (name, spec) = rest.split_once(':').ok_or("SG_ lacks ':'")?;
                if name.trim() != signal { continue; }
                let (id, message_name, byte_length) = message.clone().ok_or("SG_ appears before BO_")?;
                let mut parts = spec.split_whitespace();
                let geometry = parts.next().ok_or("SG_ lacks geometry")?;
                let (start, rest) = geometry.split_once('|').ok_or("invalid start bit")?;
                let (length, endian_sign) = rest.split_once('@').ok_or("invalid bit length")?;
                if endian_sign != "1+" { return Err(format!("unsupported geometry '@{endian_sign}': only unsigned little-endian (@1+) is implemented")); }
                let start_bit = start.parse::<u8>().map_err(|_| "invalid start bit")?;
                let length = length.parse::<u8>().map_err(|_| "invalid signal length")?;
                if length == 0 || length > 64 || start_bit as usize + length as usize > byte_length * 8 {
                    return Err("signal geometry exceeds its CAN message".into());
                }
                let scaling = parts.next().ok_or("SG_ lacks scale/offset")?.trim_start_matches('(').trim_end_matches(')');
                let (scale, offset) = scaling.split_once(',').ok_or("invalid scale/offset")?;
                let range = parts.next().ok_or("SG_ lacks range")?.trim_start_matches('[').trim_end_matches(']');
                let (minimum, maximum) = range.split_once('|').ok_or("invalid physical range")?;
                let unit = parts.next().ok_or("SG_ lacks unit")?.trim_matches('"').to_string();
                return Ok(Self {
                    message_id: id, message_name, signal_name: signal.into(), start_bit, length,
                    scale: parse_float(scale, "scale")?, offset: parse_float(offset, "offset")?,
                    minimum: parse_float(minimum, "minimum")?, maximum: parse_float(maximum, "maximum")?, unit,
                });
            }
        }
        Err(format!("signal '{signal}' was not found in {}", path.display()))
    }

    pub fn decode(&self, data: &[u8]) -> Result<(u64, f64), String> {
        let needed = (self.start_bit as usize + self.length as usize + 7) / 8;
        if data.len() < needed { return Err(format!("short CAN payload: need {needed} bytes, got {}", data.len())); }
        let mut bytes = [0u8; 8]; bytes[..data.len().min(8)].copy_from_slice(&data[..data.len().min(8)]);
        let raw = (u64::from_le_bytes(bytes) >> self.start_bit) & mask(self.length);
        Ok((raw, raw as f64 * self.scale + self.offset))
    }
}

fn mask(length: u8) -> u64 { if length == 64 { u64::MAX } else { (1u64 << length) - 1 } }
fn parse_float(value: &str, name: &str) -> Result<f64, String> {
    let parsed = value.parse::<f64>().map_err(|_| format!("invalid {name} '{value}'"))?;
    if parsed.is_finite() { Ok(parsed) } else { Err(format!("non-finite {name}")) }
}

#[derive(Clone, Debug)]
struct Frame { timestamp: String, data_hex: String }
#[derive(Clone, Debug)]
struct Sample { frame: Frame, raw: u64, physical: f64, reference: f64 }

#[derive(Clone, Debug, PartialEq)]
pub struct Report {
    pub status: String,
    pub role: String,
    pub samples: usize,
    pub mae: f64,
    pub rmse: f64,
    pub max_abs: f64,
    pub correlation: f64,
    pub fitted_scale: Option<f64>,
    pub fitted_offset: Option<f64>,
    pub reason: String,
}

impl Report {
    fn json(&self) -> Json {
        let mut fields = vec![
            ("status", Json::string(&self.status)), ("role", Json::string(&self.role)),
            ("samples", Json::number(self.samples as f64)), ("mae", Json::number(self.mae)),
            ("rmse", Json::number(self.rmse)), ("max_abs", Json::number(self.max_abs)),
            ("correlation", Json::number(self.correlation)), ("reason", Json::string(&self.reason)),
        ];
        if let Some(value) = self.fitted_scale { fields.push(("fitted_scale", Json::number(value))); }
        if let Some(value) = self.fitted_offset { fields.push(("fitted_offset", Json::number(value))); }
        Json::object(fields)
    }
}

fn capture(path: &Path, decoder: &Decoder, reference: &[Reference]) -> Result<Vec<Sample>, String> {
    let mut samples = Vec::new();
    for row in read_csv(path)? {
        let id_text = required(&row, "can_id")?;
        let id = if let Some(hex) = id_text.strip_prefix("0x") { u32::from_str_radix(hex, 16) } else { id_text.parse::<u32>() }
            .map_err(|_| format!("invalid CAN id '{id_text}'"))?;
        if id != decoder.message_id { continue; }
        let data_hex = required(&row, "data_hex")?.replace(' ', "");
        if data_hex.len() % 2 != 0 || !data_hex.bytes().all(|b| b.is_ascii_hexdigit()) { return Err("data_hex must be whole bytes".into()); }
        let mut data = Vec::new();
        for i in (0..data_hex.len()).step_by(2) { data.push(u8::from_str_radix(&data_hex[i..i + 2], 16).map_err(|_| "invalid data_hex")?); }
        let timestamp = required(&row, "timestamp")?.to_string();
        let time = timestamp_seconds(&timestamp)?;
        let reference_value = interpolate(reference, time).ok_or_else(|| format!("frame at {timestamp} is outside the reference interval"))?;
        let (raw, physical) = decoder.decode(&data)?;
        samples.push(Sample { frame: Frame { timestamp, data_hex }, raw, physical, reference: reference_value });
    }
    if samples.is_empty() { return Err(format!("no frames for 0x{:X}", decoder.message_id)); }
    Ok(samples)
}

fn correlation(samples: &[Sample]) -> f64 {
    let n = samples.len() as f64;
    let mean_x = samples.iter().map(|s| s.physical).sum::<f64>() / n;
    let mean_y = samples.iter().map(|s| s.reference).sum::<f64>() / n;
    let mut xy = 0.0; let mut xx = 0.0; let mut yy = 0.0;
    for s in samples { let x = s.physical - mean_x; let y = s.reference - mean_y; xy += x * y; xx += x * x; yy += y * y; }
    if xx == 0.0 || yy == 0.0 { 0.0 } else { xy / (xx.sqrt() * yy.sqrt()) }
}

fn metrics(samples: &[Sample]) -> (f64, f64, f64, f64) {
    let n = samples.len() as f64;
    let mae = samples.iter().map(|s| (s.physical - s.reference).abs()).sum::<f64>() / n;
    let rmse = (samples.iter().map(|s| (s.physical - s.reference).powi(2)).sum::<f64>() / n).sqrt();
    let max_abs = samples.iter().map(|s| (s.physical - s.reference).abs()).fold(0.0, f64::max);
    (mae, rmse, max_abs, correlation(samples))
}

fn linear_fit(samples: &[Sample]) -> Result<(f64, f64), String> {
    let n = samples.len() as f64;
    let mean_x = samples.iter().map(|s| s.raw as f64).sum::<f64>() / n;
    let mean_y = samples.iter().map(|s| s.reference).sum::<f64>() / n;
    let denominator = samples.iter().map(|s| (s.raw as f64 - mean_x).powi(2)).sum::<f64>();
    if denominator == 0.0 { return Err("calibration raw signal has no variation".into()); }
    let scale = samples.iter().map(|s| (s.raw as f64 - mean_x) * (s.reference - mean_y)).sum::<f64>() / denominator;
    Ok((scale, mean_y - scale * mean_x))
}

fn evaluate(samples: &[Sample], decoder: &Decoder, calibration: bool) -> Result<Report, String> {
    if samples.len() < 8 { return Err("at least eight aligned samples required".into()); }
    let (mae, rmse, max_abs, correlation) = metrics(samples);
    let (fitted_scale, fitted_offset, fit_matches) = if calibration {
        let (scale, offset) = linear_fit(samples)?;
        let matches = (scale - decoder.scale).abs() <= decoder.scale.abs().max(1.0) * 1e-6 && (offset - decoder.offset).abs() <= 0.05;
        (Some(scale), Some(offset), matches)
    } else { (None, None, false) };
    let in_range = samples.iter().all(|s| s.physical >= decoder.minimum && s.physical <= decoder.maximum);
    let absolute_ok = rmse <= 0.25 && max_abs <= 0.75 && correlation >= 0.99;
    let status = if calibration && fit_matches && absolute_ok && in_range { "CALIBRATION_ONLY" }
        else if !calibration && absolute_ok && in_range { "PASS" } else { "UNCONFIRMED" };
    let reason = if status == "PASS" { "fixed decoder agrees with independent reference in absolute units".into() }
        else if status == "CALIBRATION_ONLY" { "fit matches candidate; an independent capture is still required".into() }
        else {
            let mut causes = Vec::new();
            if !absolute_ok { causes.push(format!("absolute/correlation gates failed (RMSE {rmse:.4}, max {max_abs:.4}, r {correlation:.4})")); }
            if !in_range { causes.push("decoded value outside DBC physical range".into()); }
            if calibration && !fit_matches { causes.push("fitted scale/offset differ from candidate DBC".into()); }
            causes.join("; ")
        };
    Ok(Report { status: status.into(), role: if calibration { "calibration" } else { "holdout" }.into(),
        samples: samples.len(), mae, rmse, max_abs, correlation, fitted_scale, fitted_offset, reason })
}

fn format_number(value: f64) -> String {
    let mut out = format!("{value:.6}");
    while out.contains('.') && out.ends_with('0') { out.pop(); }
    if out.ends_with('.') { out.pop(); } out
}
fn snake_case(value: &str) -> String {
    let mut out = String::new();
    for (index, c) in value.chars().enumerate() {
        if c.is_uppercase() { if index > 0 { out.push('_'); } out.extend(c.to_lowercase()); } else { out.push(c); }
    }
    out
}

fn observation(sample: &Sample, decoder: &Decoder, report: &Report, machine: &str,
               context: &str, simulated: bool, dbc: &Path, reference: &Path, reference_source: &str) -> Json {
    let verified = report.status == "PASS" || report.status == "CALIBRATION_ONLY";
    let (kind, value, unit) = if verified {
        (snake_case(&decoder.signal_name), format_number(sample.physical), decoder.unit.clone())
    } else {
        (format!("can_frame_0x{:X}", decoder.message_id), sample.frame.data_hex.clone(), String::new())
    };
    Json::object(vec![
        ("timestamp", Json::string(&sample.frame.timestamp)), ("machine", Json::string(machine)),
        ("kind", Json::string(kind)), ("value", Json::string(value)), ("unit", Json::string(unit)),
        ("source", Json::string("can-dbc-replay")), ("context", Json::string(context)),
        ("simulated", Json::Bool(simulated)),
        ("details", Json::object(vec![
            ("can_id", Json::string(format!("0x{:X}", decoder.message_id))),
            ("raw_hex", Json::string(&sample.frame.data_hex)), ("raw_value", Json::number(sample.raw as f64)),
            ("decode", Json::string(if verified { "dbc-candidate" } else { "raw-unresolved" })),
            ("verification", Json::string(&report.status)), ("candidate_signal", Json::string(&decoder.signal_name)),
            ("decoder", Json::string(dbc.display().to_string())), ("reference", Json::string(reference.display().to_string())),
            ("reference_source", Json::string(reference_source)), ("reference_unit", Json::string(&decoder.unit)),
            ("reference_alignment", Json::string("linear interpolation on UTC timestamps")),
            ("reference_uncertainty", Json::string("not supplied; not estimated by replay")),
            ("start_bit", Json::number(decoder.start_bit as f64)), ("length", Json::number(decoder.length as f64)),
            ("scale", Json::number(decoder.scale)), ("offset", Json::number(decoder.offset)),
        ])),
    ])
}

pub fn run_can(capture_path: &Path, reference_path: &Path, dbc_path: &Path, signal: &str,
               machine: &str, context: &str, simulated: bool, calibration: bool,
               output: &Path) -> Result<Report, String> {
    let decoder = Decoder::from_dbc(dbc_path, signal)?;
    let reference = references(reference_path, &decoder.unit)?;
    let ref_source = reference_source(reference_path)?;
    let samples = capture(capture_path, &decoder, &reference)?;
    let report = evaluate(&samples, &decoder, calibration)?;
    let mut records: Vec<Json> = samples.iter()
        .map(|s| observation(s, &decoder, &report, machine, context, simulated, dbc_path, reference_path, &ref_source)).collect();
    let last = samples.last().unwrap();
    records.push(Json::object(vec![
        ("timestamp", Json::string(&last.frame.timestamp)), ("machine", Json::string(machine)),
        ("kind", Json::string("decoder_verification")), ("value", Json::string(&report.status)),
        ("unit", Json::string("")), ("source", Json::string("caretaker-replay")),
        ("context", Json::string(context)), ("simulated", Json::Bool(simulated)),
        ("details", report.json()),
    ]));
    write_jsonl(output, &records)?;
    Ok(report)
}

pub fn import_jsonl(input: &Path, output: &Path) -> Result<usize, String> {
    let text = fs::read_to_string(input).map_err(|e| format!("{}: {e}", input.display()))?;
    let mut records = Vec::new();
    for (index, line) in text.lines().enumerate() {
        if line.trim().is_empty() { continue; }
        let value = json::parse(line).map_err(|e| format!("{}:{}: {e}", input.display(), index + 1))?;
        let object = value.as_object().ok_or("JSONL record must be an object")?;
        for key in ["timestamp", "machine", "kind", "value", "unit", "source", "context"] {
            if !matches!(object.get(key), Some(Json::String(_))) { return Err(format!("{}:{}: '{key}' must be a string", input.display(), index + 1)); }
        }
        if !matches!(object.get("simulated"), Some(Json::Bool(_))) { return Err(format!("{}:{}: 'simulated' must be boolean", input.display(), index + 1)); }
        records.push(value);
    }
    write_jsonl(output, &records)?; Ok(records.len())
}

fn write_jsonl(path: &Path, records: &[Json]) -> Result<(), String> {
    if let Some(parent) = path.parent() { fs::create_dir_all(parent).map_err(|e| format!("{}: {e}", parent.display()))?; }
    let text = records.iter().map(|r| r.dump() + "\n").collect::<String>();
    fs::write(path, text).map_err(|e| format!("{}: {e}", path.display()))
}

pub fn fixture_path(name: &str) -> PathBuf { Path::new(env!("CARGO_MANIFEST_DIR")).join("fixtures").join(name) }

#[cfg(test)]
mod tests {
    use super::*;
    fn temp(name: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!("caretaker-replay-{}-{}", std::process::id(), name));
        fs::create_dir_all(&dir).unwrap(); dir
    }
    #[test] fn decodes_unsigned_little_endian_signal() {
        let d = Decoder::from_dbc(&fixture_path("vehicle-speed.dbc"), "VehicleSpeed").unwrap();
        assert_eq!(d.message_id, 0x123); assert_eq!(d.decode(&[0x10, 0x27, 0, 0, 0, 0, 0, 0]).unwrap(), (10000, 100.0));
    }
    #[test] fn calibration_fit_and_independent_holdout_pass() {
        let dir = temp("pass");
        let calibration = run_can(&fixture_path("can-calibration.csv"), &fixture_path("can-calibration-reference.csv"),
            &fixture_path("vehicle-speed.dbc"), "VehicleSpeed", "demo-can", "synthetic", true, true, &dir.join("cal.jsonl")).unwrap();
        assert_eq!(calibration.status, "CALIBRATION_ONLY");
        assert!((calibration.fitted_scale.unwrap() - 0.01).abs() < 1e-9);
        let holdout = run_can(&fixture_path("can-holdout.csv"), &fixture_path("can-holdout-reference.csv"),
            &fixture_path("vehicle-speed.dbc"), "VehicleSpeed", "demo-can", "synthetic", true, false, &dir.join("holdout.jsonl")).unwrap();
        assert_eq!(holdout.status, "PASS"); assert_eq!(holdout.samples, 30); assert!(holdout.rmse < 1e-9);
    }
    #[test] fn plausible_wrong_field_is_unconfirmed_and_stays_raw() {
        let dir = temp("wrong");
        let report = run_can(&fixture_path("can-holdout.csv"), &fixture_path("can-holdout-reference.csv"),
            &fixture_path("wrong-vehicle-speed.dbc"), "VehicleSpeed", "demo-can", "synthetic", true, false, &dir.join("wrong.jsonl")).unwrap();
        assert_eq!(report.status, "UNCONFIRMED");
        let text = fs::read_to_string(dir.join("wrong.jsonl")).unwrap();
        let rows: Vec<Json> = text.lines().map(|l| json::parse(l).unwrap()).collect();
        assert!(rows.iter().all(|r| r.get("kind").unwrap().as_str().unwrap() != "vehicle_speed"));
        assert!(rows.iter().any(|r| r.get("kind").unwrap().as_str().unwrap() == "can_frame_0x123"));
        assert!(text.contains("raw-unresolved"));
    }
    #[test] fn t4_existing_demo_round_trips_semantically() {
        let dir = temp("t4"); let output = dir.join("t4.jsonl");
        let count = import_jsonl(&fixture_path("t4-demo.jsonl"), &output).unwrap(); assert_eq!(count, 6);
        let original = fs::read_to_string(fixture_path("t4-demo.jsonl")).unwrap();
        let replayed = fs::read_to_string(output).unwrap();
        let a: Vec<Json> = original.lines().map(|l| json::parse(l).unwrap()).collect();
        let b: Vec<Json> = replayed.lines().map(|l| json::parse(l).unwrap()).collect();
        assert_eq!(a, b); assert!(b.iter().all(|r| r.get("simulated").unwrap().as_bool() == Some(true)));
    }
    #[test] fn rejects_unsupported_dbc_endianness() {
        let dir = temp("dbc"); let path = dir.join("bad.dbc");
        fs::write(&path, "BO_ 291 M: 8 X\n SG_ S : 7|8@0+ (1,0) [0|1] \"V\" X\n").unwrap();
        assert!(Decoder::from_dbc(&path, "S").unwrap_err().contains("only unsigned little-endian"));
    }
}
