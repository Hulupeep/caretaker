//! Minimal JSON representation for dependency-free, offline replay.
//! It intentionally supports the complete JSON syntax used by Caretaker JSONL,
//! rather than searching for field names in raw strings.

use std::collections::BTreeMap;

#[derive(Clone, Debug, PartialEq)]
pub enum Json {
    Null,
    Bool(bool),
    Number(f64),
    String(String),
    Array(Vec<Json>),
    Object(BTreeMap<String, Json>),
}

impl Json {
    pub fn string(value: impl Into<String>) -> Self { Self::String(value.into()) }
    pub fn number(value: f64) -> Self { Self::Number(value) }
    pub fn object(entries: Vec<(&str, Json)>) -> Self {
        Self::Object(entries.into_iter().map(|(k, v)| (k.to_string(), v)).collect())
    }
    pub fn as_object(&self) -> Option<&BTreeMap<String, Json>> {
        match self { Self::Object(value) => Some(value), _ => None }
    }
    pub fn get(&self, key: &str) -> Option<&Json> { self.as_object()?.get(key) }
    pub fn as_str(&self) -> Option<&str> {
        match self { Self::String(value) => Some(value), _ => None }
    }
    pub fn as_bool(&self) -> Option<bool> {
        match self { Self::Bool(value) => Some(*value), _ => None }
    }
    pub fn dump(&self) -> String {
        match self {
            Self::Null => "null".into(),
            Self::Bool(value) => value.to_string(),
            Self::Number(value) => {
                if !value.is_finite() { return "null".into(); }
                if value.fract() == 0.0 && value.abs() < 9_007_199_254_740_992.0 {
                    format!("{value:.0}")
                } else { value.to_string() }
            }
            Self::String(value) => quote(value),
            Self::Array(values) => format!("[{}]", values.iter().map(Self::dump).collect::<Vec<_>>().join(",")),
            Self::Object(values) => format!("{{{}}}", values.iter()
                .map(|(key, value)| format!("{}:{}", quote(key), value.dump()))
                .collect::<Vec<_>>().join(",")),
        }
    }
}

fn quote(value: &str) -> String {
    let mut out = String::from("\"");
    for c in value.chars() {
        match c {
            '\"' => out.push_str("\\\""), '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"), '\r' => out.push_str("\\r"), '\t' => out.push_str("\\t"),
            c if c < ' ' => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('\"');
    out
}

pub fn parse(input: &str) -> Result<Json, String> {
    let mut parser = Parser { bytes: input.as_bytes(), pos: 0 };
    let value = parser.value()?;
    parser.space();
    if parser.pos != parser.bytes.len() { return Err(format!("trailing JSON at byte {}", parser.pos)); }
    Ok(value)
}

struct Parser<'a> { bytes: &'a [u8], pos: usize }
impl<'a> Parser<'a> {
    fn space(&mut self) { while self.pos < self.bytes.len() && self.bytes[self.pos].is_ascii_whitespace() { self.pos += 1; } }
    fn value(&mut self) -> Result<Json, String> {
        self.space();
        match self.bytes.get(self.pos).copied() {
            Some(b'n') => { self.literal(b"null")?; Ok(Json::Null) }
            Some(b't') => { self.literal(b"true")?; Ok(Json::Bool(true)) }
            Some(b'f') => { self.literal(b"false")?; Ok(Json::Bool(false)) }
            Some(b'\"') => Ok(Json::String(self.string()?)),
            Some(b'[') => self.array(), Some(b'{') => self.object(),
            Some(b'-' | b'0'..=b'9') => self.number(),
            _ => Err(format!("expected JSON value at byte {}", self.pos)),
        }
    }
    fn literal(&mut self, expected: &[u8]) -> Result<(), String> {
        if self.bytes.get(self.pos..self.pos + expected.len()) == Some(expected) {
            self.pos += expected.len(); Ok(())
        } else { Err(format!("invalid literal at byte {}", self.pos)) }
    }
    fn string(&mut self) -> Result<String, String> {
        self.pos += 1;
        let mut out = String::new();
        while let Some(byte) = self.bytes.get(self.pos).copied() {
            self.pos += 1;
            match byte {
                b'\"' => return Ok(out),
                b'\\' => {
                    let escaped = self.bytes.get(self.pos).copied().ok_or("unterminated escape")?;
                    self.pos += 1;
                    match escaped {
                        b'\"' => out.push('\"'), b'\\' => out.push('\\'), b'/' => out.push('/'),
                        b'b' => out.push('\u{8}'), b'f' => out.push('\u{c}'), b'n' => out.push('\n'),
                        b'r' => out.push('\r'), b't' => out.push('\t'),
                        b'u' => {
                            let first = self.hex4()?;
                            let scalar = if (0xD800..=0xDBFF).contains(&first) {
                                if self.bytes.get(self.pos..self.pos + 2) != Some(b"\\u") { return Err("missing low surrogate".into()); }
                                self.pos += 2;
                                let second = self.hex4()?;
                                if !(0xDC00..=0xDFFF).contains(&second) { return Err("invalid low surrogate".into()); }
                                0x10000 + ((first - 0xD800) << 10) + (second - 0xDC00)
                            } else { first };
                            out.push(char::from_u32(scalar).ok_or("invalid Unicode escape")?);
                        }
                        _ => return Err(format!("invalid escape at byte {}", self.pos - 1)),
                    }
                }
                0..=31 => return Err("control character in JSON string".into()),
                _ => {
                    let start = self.pos - 1;
                    let width = utf8_width(byte)?;
                    if width > 1 {
                        if self.bytes.get(start..start + width).is_none() { return Err("truncated UTF-8".into()); }
                        self.pos = start + width;
                    }
                    out.push_str(std::str::from_utf8(&self.bytes[start..self.pos]).map_err(|_| "invalid UTF-8")?);
                }
            }
        }
        Err("unterminated JSON string".into())
    }
    fn hex4(&mut self) -> Result<u32, String> {
        let text = std::str::from_utf8(self.bytes.get(self.pos..self.pos + 4).ok_or("short Unicode escape")?).map_err(|_| "invalid escape")?;
        self.pos += 4;
        u32::from_str_radix(text, 16).map_err(|_| "invalid Unicode escape".into())
    }
    fn array(&mut self) -> Result<Json, String> {
        self.pos += 1; let mut values = Vec::new(); self.space();
        if self.bytes.get(self.pos) == Some(&b']') { self.pos += 1; return Ok(Json::Array(values)); }
        loop {
            values.push(self.value()?); self.space();
            match self.bytes.get(self.pos) { Some(b',') => self.pos += 1, Some(b']') => { self.pos += 1; break; }, _ => return Err("expected ',' or ']'".into()) }
        }
        Ok(Json::Array(values))
    }
    fn object(&mut self) -> Result<Json, String> {
        self.pos += 1; let mut values = BTreeMap::new(); self.space();
        if self.bytes.get(self.pos) == Some(&b'}') { self.pos += 1; return Ok(Json::Object(values)); }
        loop {
            self.space(); if self.bytes.get(self.pos) != Some(&b'\"') { return Err("expected object key".into()); }
            let key = self.string()?; self.space();
            if self.bytes.get(self.pos) != Some(&b':') { return Err("expected ':'".into()); }
            self.pos += 1; values.insert(key, self.value()?); self.space();
            match self.bytes.get(self.pos) { Some(b',') => self.pos += 1, Some(b'}') => { self.pos += 1; break; }, _ => return Err("expected ',' or '}'".into()) }
        }
        Ok(Json::Object(values))
    }
    fn number(&mut self) -> Result<Json, String> {
        let start = self.pos;
        while self.pos < self.bytes.len() && matches!(self.bytes[self.pos], b'-' | b'+' | b'.' | b'e' | b'E' | b'0'..=b'9') { self.pos += 1; }
        let text = std::str::from_utf8(&self.bytes[start..self.pos]).map_err(|_| "invalid number")?;
        let value = text.parse::<f64>().map_err(|_| format!("invalid JSON number '{text}'"))?;
        if !value.is_finite() { return Err("non-finite JSON number".into()); }
        Ok(Json::Number(value))
    }
}
fn utf8_width(byte: u8) -> Result<usize, String> {
    match byte { 0x00..=0x7f => Ok(1), 0xc2..=0xdf => Ok(2), 0xe0..=0xef => Ok(3), 0xf0..=0xf4 => Ok(4), _ => Err("invalid UTF-8 start".into()) }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test] fn round_trip_caretaker_unicode_and_escapes() {
        let input = r#"{"a":"°C\n\"x\"","b":[true,null,-1.25e2],"c":"\ud83d\ude00"}"#;
        let value = parse(input).unwrap();
        assert_eq!(parse(&value.dump()).unwrap(), value);
    }
}
