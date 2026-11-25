use std::collections::BTreeMap;
use std::fs;
use std::path::Path;

pub type Row = BTreeMap<String, String>;

pub fn read_csv(path: &Path) -> Result<Vec<Row>, String> {
    let text = fs::read_to_string(path).map_err(|e| format!("{}: {e}", path.display()))?;
    let mut lines = text.lines();
    let header = parse_csv_line(lines.next().ok_or("empty CSV")?)?;
    if header.iter().any(|h| h.is_empty()) { return Err(format!("{}: empty CSV header", path.display())); }
    let mut rows = Vec::new();
    for (index, line) in lines.enumerate() {
        if line.trim().is_empty() { continue; }
        let values = parse_csv_line(line)?;
        if values.len() != header.len() { return Err(format!("{}:{}: expected {} columns, got {}", path.display(), index + 2, header.len(), values.len())); }
        rows.push(header.iter().cloned().zip(values).collect());
    }
    Ok(rows)
}

fn parse_csv_line(line: &str) -> Result<Vec<String>, String> {
    let mut fields = Vec::new(); let mut field = String::new();
    let mut chars = line.chars().peekable(); let mut quoted = false;
    while let Some(c) = chars.next() {
        match c {
            '"' if quoted && chars.peek() == Some(&'"') => { field.push('"'); chars.next(); }
            '"' => quoted = !quoted,
            ',' if !quoted => { fields.push(std::mem::take(&mut field)); }
            '\r' | '\n' => return Err("embedded CSV newlines are not supported".into()),
            c => field.push(c),
        }
    }
    if quoted { return Err("unterminated quoted CSV field".into()); }
    fields.push(field); Ok(fields)
}

pub fn required<'a>(row: &'a Row, key: &str) -> Result<&'a str, String> {
    row.get(key).map(String::as_str).ok_or_else(|| format!("missing CSV column '{key}'"))
}

pub fn timestamp_seconds(value: &str) -> Result<f64, String> {
    // Supported interchange form: YYYY-MM-DDTHH:MM:SS[.fraction]Z.
    // Offset-bearing input remains valid in T4 JSONL; CAN replay deliberately
    // rejects non-UTC input rather than silently mis-aligning a reference.
    let (date, time) = value.split_once('T').ok_or_else(|| format!("timestamp '{value}' lacks T"))?;
    let time = time.strip_suffix('Z').ok_or_else(|| format!("CAN timestamp '{value}' must end in Z"))?;
    let mut d = date.split('-');
    let year: i64 = d.next().ok_or("missing year")?.parse().map_err(|_| "invalid year")?;
    let month: i64 = d.next().ok_or("missing month")?.parse().map_err(|_| "invalid month")?;
    let day: i64 = d.next().ok_or("missing day")?.parse().map_err(|_| "invalid day")?;
    if d.next().is_some() || !(1..=12).contains(&month) || !(1..=31).contains(&day) { return Err(format!("invalid date '{date}'")); }
    let mut t = time.split(':');
    let hour: f64 = t.next().ok_or("missing hour")?.parse().map_err(|_| "invalid hour")?;
    let minute: f64 = t.next().ok_or("missing minute")?.parse().map_err(|_| "invalid minute")?;
    let second: f64 = t.next().ok_or("missing second")?.parse().map_err(|_| "invalid second")?;
    if t.next().is_some() || hour > 23.0 || minute > 59.0 || !(0.0..61.0).contains(&second) { return Err(format!("invalid time '{time}'")); }
    Ok(days_from_civil(year, month, day) as f64 * 86400.0 + hour * 3600.0 + minute * 60.0 + second)
}

// Howard Hinnant's civil-date conversion, with 1970-01-01 as day zero.
fn days_from_civil(year: i64, month: i64, day: i64) -> i64 {
    let y = year - if month <= 2 { 1 } else { 0 };
    let era = if y >= 0 { y } else { y - 399 } / 400;
    let yoe = y - era * 400;
    let mp = month + if month > 2 { -3 } else { 9 };
    let doy = (153 * mp + 2) / 5 + day - 1;
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    era * 146097 + doe - 719468
}

#[derive(Clone, Debug)]
pub struct Reference { pub time: f64, pub value: f64 }

pub fn reference_source(path: &Path) -> Result<String, String> {
    let rows = read_csv(path)?;
    let mut sources = rows.iter().map(|row| required(row, "source")).collect::<Result<Vec<_>, _>>()?;
    sources.sort(); sources.dedup();
    if sources.len() != 1 { return Err(format!("{}: reference must have one consistent source", path.display())); }
    Ok(sources[0].to_string())
}

pub fn references(path: &Path, expected_unit: &str) -> Result<Vec<Reference>, String> {
    let mut out = Vec::new();
    for row in read_csv(path)? {
        let unit = required(&row, "unit")?;
        if unit != expected_unit { return Err(format!("{}: reference unit '{unit}' does not match decoder unit '{expected_unit}'", path.display())); }
        let source = required(&row, "source")?;
        if source.trim().is_empty() { return Err(format!("{}: empty reference source", path.display())); }
        out.push(Reference {
            time: timestamp_seconds(required(&row, "timestamp")?)?,
            value: required(&row, "value")?.parse::<f64>().map_err(|_| "reference value is not numeric")?,
        });
    }
    if out.len() < 2 { return Err("at least two reference samples required".into()); }
    out.sort_by(|a, b| a.time.partial_cmp(&b.time).unwrap());
    if out.windows(2).any(|w| w[0].time == w[1].time) { return Err("duplicate reference timestamps".into()); }
    Ok(out)
}

pub fn interpolate(reference: &[Reference], time: f64) -> Option<f64> {
    if time < reference.first()?.time || time > reference.last()?.time { return None; }
    match reference.binary_search_by(|r| r.time.partial_cmp(&time).unwrap()) {
        Ok(index) => Some(reference[index].value),
        Err(index) => {
            let a = &reference[index - 1]; let b = &reference[index];
            Some(a.value + (b.value - a.value) * (time - a.time) / (b.time - a.time))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test] fn epoch_and_interpolation() {
        assert_eq!(timestamp_seconds("1970-01-01T00:00:00Z").unwrap(), 0.0);
        assert_eq!(timestamp_seconds("1970-01-02T00:00:00.500Z").unwrap(), 86400.5);
        let r = vec![Reference { time: 0.0, value: 0.0 }, Reference { time: 2.0, value: 10.0 }];
        assert_eq!(interpolate(&r, 1.0), Some(5.0)); assert_eq!(interpolate(&r, 3.0), None);
    }
}
