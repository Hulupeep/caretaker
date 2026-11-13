use caretaker_replay::{import_jsonl, run_can, Report};
use std::collections::{BTreeMap, HashSet};
use std::env;
use std::path::{Path, PathBuf};
use std::process;

const HELP: &str = "Caretaker offline replay (no hardware access)\n\
\n\
USAGE:\n\
  caretaker-replay can --capture CSV --reference CSV --dbc FILE --signal NAME \\\n\
      --output JSONL [--machine ID] [--context TEXT] [--calibration] [--simulated]\n\
  caretaker-replay t4 --input JSONL --output JSONL\n\
  caretaker-replay demo --fixtures DIR --output DIR [--t4-input JSONL]\n\
\n\
CAN CSV columns: timestamp (UTC ISO-8601), can_id, data_hex.\n\
Reference CSV columns: timestamp, value, unit, source.\n\
Only unsigned little-endian DBC signals (@1+) are supported in this prototype.\n\
UNCONFIRMED is a valid verification outcome; frames remain raw and unnamed.\n";

struct Args { options: BTreeMap<String, String>, flags: HashSet<String> }
impl Args {
    fn parse(mut values: Vec<String>) -> Result<Self, String> {
        let mut options = BTreeMap::new(); let mut flags = HashSet::new();
        while !values.is_empty() {
            let key = values.remove(0);
            if !key.starts_with("--") { return Err(format!("unexpected argument '{key}'")); }
            if ["--calibration", "--simulated"].contains(&key.as_str()) { flags.insert(key); continue; }
            if values.is_empty() { return Err(format!("{key} requires a value")); }
            options.insert(key, values.remove(0));
        }
        Ok(Self { options, flags })
    }
    fn get(&self, key: &str) -> Result<&str, String> { self.options.get(key).map(String::as_str).ok_or_else(|| format!("missing {key}")) }
    fn or<'a>(&'a self, key: &str, default: &'a str) -> &'a str { self.options.get(key).map(String::as_str).unwrap_or(default) }
    fn flag(&self, key: &str) -> bool { self.flags.contains(key) }
}

fn print_report(label: &str, report: &Report) {
    println!("{label}: {} ({} samples, RMSE {:.6}, max abs {:.6}, r {:.6})",
        report.status, report.samples, report.rmse, report.max_abs, report.correlation);
    if let (Some(scale), Some(offset)) = (report.fitted_scale, report.fitted_offset) {
        println!("  calibration fit: scale={scale:.9}, offset={offset:.9}");
    }
    println!("  {}", report.reason);
}

fn run() -> Result<i32, String> {
    let mut argv: Vec<String> = env::args().skip(1).collect();
    if argv.is_empty() || argv[0] == "--help" || argv[0] == "-h" { print!("{HELP}"); return Ok(0); }
    let command = argv.remove(0); let args = Args::parse(argv)?;
    match command.as_str() {
        "can" => {
            let report = run_can(Path::new(args.get("--capture")?), Path::new(args.get("--reference")?),
                Path::new(args.get("--dbc")?), args.get("--signal")?, args.or("--machine", "machine-1"),
                args.or("--context", "offline replay"), args.flag("--simulated"), args.flag("--calibration"),
                Path::new(args.get("--output")?))?;
            print_report("CAN", &report);
            Ok(if report.status == "UNCONFIRMED" { 2 } else { 0 })
        }
        "t4" => {
            let count = import_jsonl(Path::new(args.get("--input")?), Path::new(args.get("--output")?))?;
            println!("T4/JSONL: PASS ({count} records preserved with source, units, details, and simulated flags)");
            Ok(0)
        }
        "demo" => {
            let fixtures = PathBuf::from(args.get("--fixtures")?);
            let output = PathBuf::from(args.get("--output")?);
            let t4_input = args.options.get("--t4-input").map(PathBuf::from).unwrap_or_else(|| fixtures.join("t4-demo.jsonl"));
            let calibration = run_can(&fixtures.join("can-calibration.csv"), &fixtures.join("can-calibration-reference.csv"),
                &fixtures.join("vehicle-speed.dbc"), "VehicleSpeed", "demo-can", "SYNTHETIC calibration fixture; not a vehicle capture",
                true, true, &output.join("can-calibration.jsonl"))?;
            print_report("CAN calibration", &calibration);
            let holdout = run_can(&fixtures.join("can-holdout.csv"), &fixtures.join("can-holdout-reference.csv"),
                &fixtures.join("vehicle-speed.dbc"), "VehicleSpeed", "demo-can", "SYNTHETIC independent holdout fixture",
                true, false, &output.join("can-holdout.jsonl"))?;
            print_report("CAN holdout", &holdout);
            let wrong = run_can(&fixtures.join("can-holdout.csv"), &fixtures.join("can-holdout-reference.csv"),
                &fixtures.join("wrong-vehicle-speed.dbc"), "VehicleSpeed", "demo-can-wrong", "SYNTHETIC plausible wrong bit field",
                true, false, &output.join("can-wrong-match.jsonl"))?;
            print_report("CAN wrong match", &wrong);
            let count = import_jsonl(&t4_input, &output.join("t4-replayed.jsonl"))?;
            println!("T4/JSONL: PASS ({count} records preserved; source records remain simulated={}", true);
            if calibration.status != "CALIBRATION_ONLY" || holdout.status != "PASS" || wrong.status != "UNCONFIRMED" || count != 6 {
                return Err("demo produced an unexpected verification outcome".into());
            }
            println!("Expected negative case remained UNCONFIRMED; outputs are in {}", output.display());
            Ok(0)
        }
        _ => Err(format!("unknown command '{command}'\n\n{HELP}")),
    }
}

fn main() {
    match run() {
        Ok(code) => process::exit(code),
        Err(error) => { eprintln!("caretaker-replay: {error}"); process::exit(1); }
    }
}
