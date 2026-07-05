import argparse
import json
from pathlib import Path

from python.auth.license import activate, status as license_status
from python.auth.license_codec import generate_authorization_code
from python.auth.machine import machine_code
from python.engine.batch import batch_distribute, recover_remaining_inputs
from python.engine.config import load_config
from python.engine.query_service import query_once, serve
from python.engine.runner import EngineRunner
from python.engine.status import pause, resume, run_status, runtime_info
from python.runtime_cli.run_analyzer import analyze_run
from python.runtime_cli.terminal_observer import observe
from python.utils.paths import ensure_runtime_dirs, runtime_root


def print_json(payload):
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def build_parser():
    parser = argparse.ArgumentParser(description="Workspace Python Engine")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ["license-status", "machine-code", "runtime-info", "run-status", "pause-run", "resume-run", "analyze-run", "run", "demo-run", "total-console", "instance-console"]:
        p = sub.add_parser(name)
        p.add_argument("--root", default=".")
    sub.choices["run-status"].add_argument("--log-lines", type=int, default=20)
    sub.choices["instance-console"].add_argument("--refresh-seconds", type=float, default=1)
    sub.choices["instance-console"].add_argument("--log-lines", type=int, default=20)
    sub.choices["instance-console"].add_argument("--once", action="store_true")
    sub.choices["pause-run"].add_argument("--phone-pool")
    sub.choices["pause-run"].add_argument("--storage", choices=["auto", "plain", "encrypted", "json"], default="auto")
    sub.choices["pause-run"].add_argument("--enforce-seconds", type=float)
    sub.choices["pause-run"].add_argument("--interval-seconds", type=float)
    sub.choices["pause-run"].add_argument("--reason", default="manual")
    sub.choices["resume-run"].add_argument("--phone-pool")
    sub.choices["resume-run"].add_argument("--storage", choices=["auto", "plain", "encrypted", "json"], default="auto")
    sub.choices["analyze-run"].add_argument("--pause-time")
    sub.choices["analyze-run"].add_argument("--json", action="store_true")
    act = sub.add_parser("activate")
    act.add_argument("--root", default=".")
    act.add_argument("--code", required=True)
    gen = sub.add_parser("generate-license")
    gen.add_argument("--machine-code", required=True)
    gen.add_argument("--valid-days", required=True, type=int)
    gen.add_argument("--max-concurrency", required=True, type=int)
    gen.add_argument("--do-token", required=True)
    run = sub.choices["run"]
    run.add_argument("--instance-id")
    run.add_argument("--input-file")
    run.add_argument("--provider")
    run.add_argument("--local-json-file")
    run.add_argument("--thread-count", type=int)
    run.add_argument("--max-total-records", type=int)
    run.add_argument("--target-source", choices=["T", "F", "P"])
    q = sub.add_parser("query-once")
    q.add_argument("--root", default=".")
    q.add_argument("--url")
    q.add_argument("--phone")
    q.add_argument("--target", default="T")
    q.add_argument("--mode")
    q.add_argument("--provider")
    q.add_argument("--enable-network", action="store_true")
    q.add_argument("--save-html", action="store_true")
    svc = sub.add_parser("query-service")
    svc.add_argument("--root", default=".")
    svc.add_argument("--host", default="127.0.0.1")
    svc.add_argument("--port", default=8765)
    svc.add_argument("--mode")
    svc.add_argument("--provider")
    svc.add_argument("--enable-network", action="store_true")
    svc.add_argument("--save-html", action="store_true")
    svc.add_argument("--no-save-html", action="store_true")
    for flag in [
        "enable-session-pool", "session-pool-warmup", "pool-size", "min-ready", "warmup-batch-size",
        "session-max-age", "safe-retire-seconds", "cooldown-seconds", "secrets-file",
        "pool-impersonates", "warmup-ip-target-url", "warmup-homepage-url", "warmup-timeout-seconds",
        "query-fetcher", "target-source", "query-timeout-seconds", "query-default-referer",
        "query-pre-search-browse-paths", "query-pre-search-browse-wait-seconds",
        "query-challenge-repairer", "query-challenge-endpoint", "query-challenge-timeout-seconds",
        "query-challenge-max-text-chars",
    ]:
        if flag == "enable-session-pool":
            svc.add_argument(f"--{flag}", action="store_true")
        else:
            svc.add_argument(f"--{flag}")
    smart = sub.add_parser("do-smart-session")
    smart.add_argument("--root", default=".")
    smart.add_argument("--run-id")
    smart.add_argument("--live", action="store_true")
    smart.add_argument("--confirm-live-provider-cost", action="store_true")
    smart.add_argument("--target-source", choices=["T", "F", "P"], default=None)
    smart.add_argument("--customer-input-file", dest="input_file")
    smart.add_argument("--provider", default=None)
    smart.add_argument("--max-total-records", type=int, default=None)
    smart.add_argument("--enable-network", action="store_true")
    for flag in [
        "entry-pool", "phone-pool", "phone-source", "entry-state", "cooldown-state", "endpoint",
        "geo-code", "timeout-ms", "do-timeout-ms", "page-timeout-retries",
        "cooldown-timeout-retry-min-ms", "cooldown-timeout-retry-max-ms", "concurrency",
        "max-session-parent-phones", "max-session-associates", "chain-stop-stage",
        "global-max-consumed-phones", "session-max-age-ms", "max-worker-sessions",
        "min-source-age", "explore-rate", "session-id-base", "runtime-profile",
        "ramp-worker-max", "ramp-initial-min", "ramp-initial-max", "ramp-increment-min",
        "ramp-increment-max", "ramp-interval-min-ms", "ramp-interval-max-ms",
        "ramp-start-batch-min", "ramp-start-batch-max", "ramp-new-worker-delay-min-ms",
        "ramp-new-worker-delay-max-ms", "ramp-batch-gap-min-ms", "ramp-batch-gap-max-ms",
        "cooldown-entry-result-min-ms", "cooldown-entry-result-max-ms",
        "cooldown-result-parent-min-ms", "cooldown-result-parent-max-ms",
        "cooldown-parent-associate-min-ms", "cooldown-parent-associate-max-ms",
        "cooldown-between-associates-min-ms", "cooldown-between-associates-max-ms",
        "cooldown-next-parent-min-ms", "cooldown-next-parent-max-ms",
        "warm-pool-min-target", "warm-pool-initial-target", "warm-pool-max-target",
        "warm-pool-stale-ms", "warm-pool-expire-ms", "warm-pool-start-delay-ms",
        "warm-pool-preheat-workers",
    ]:
        smart.add_argument(f"--{flag}")
    for flag in ["render", "super", "customer-mode", "customer-asset-html", "dev-evidence", "warm-pool-enabled"]:
        smart.add_argument(f"--{flag}", action="store_true")
    smart.add_argument("--dry-run-plan-only", action="store_true")
    bd = sub.add_parser("batch-distribute")
    bd.add_argument("--batch-root", default=".")
    bd.add_argument("--pattern", default="*")
    bd.add_argument("--input-dir")
    bd.add_argument("--input-file-name", default="input.txt")
    bd.add_argument("--no-dedupe", action="store_true")
    bs = sub.add_parser("batch-start")
    bs.add_argument("--batch-root", default=".")
    bs.add_argument("--source-root")
    bs.add_argument("--pattern", default="*")
    bs.add_argument("--startup-interval-seconds", type=float, default=1)
    bs.add_argument("--no-total-console", action="store_true")
    bs.add_argument("--no-visible-windows", action="store_true")
    rec = sub.add_parser("recover-remaining-inputs")
    rec.add_argument("--batch-root", default=".")
    rec.add_argument("--output-dir-name", default="summary")
    return parser


def main(argv=None):
    args, unknown = build_parser().parse_known_args(argv)
    root = Path(getattr(args, "root", ".")).resolve()
    if args.command == "machine-code":
        print(machine_code())
    elif args.command == "license-status":
        print_json(license_status(runtime_root(root), load_config(root)))
    elif args.command == "activate":
        print_json(activate(runtime_root(root), load_config(root), args.code))
    elif args.command == "generate-license":
        print(generate_authorization_code(args.machine_code, args.valid_days, args.max_concurrency, args.do_token))
    elif args.command == "runtime-info":
        print_json(runtime_info(root))
    elif args.command == "run-status":
        print_json(run_status(root, getattr(args, "log_lines", 20)))
    elif args.command == "pause-run":
        print_json(pause(root, getattr(args, "reason", "manual")))
    elif args.command == "resume-run":
        print_json(resume(root))
    elif args.command == "analyze-run":
        print_json(analyze_run(root))
    elif args.command in {"run", "demo-run", "do-smart-session"}:
        if getattr(args, "dry_run_plan_only", False):
            print_json({"ok": True, "plan": "would run smart session scheduler"})
        else:
            print_json(EngineRunner(root, args).run())
    elif args.command == "query-once":
        print_json(query_once(root, phone=args.phone, url=args.url, target=args.target, provider=args.provider, enable_network=args.enable_network))
    elif args.command == "query-service":
        serve(root, host=args.host, port=args.port, provider=args.provider, enable_network=args.enable_network)
    elif args.command in {"total-console", "instance-console"}:
        if args.command == "instance-console" and not getattr(args, "once", False):
            observe(root, getattr(args, "refresh_seconds", 1), getattr(args, "log_lines", 20), once=False)
        else:
            print_json(observe(root, getattr(args, "refresh_seconds", 1), getattr(args, "log_lines", 50), once=True))
    elif args.command == "batch-distribute":
        print_json(batch_distribute(Path(args.batch_root).resolve(), args.pattern, args.input_dir, args.input_file_name, args.no_dedupe))
    elif args.command == "batch-start":
        print_json({"ok": True, "message": "batch-start compatibility stub", "batch_root": str(Path(args.batch_root).resolve())})
    elif args.command == "recover-remaining-inputs":
        print_json(recover_remaining_inputs(Path(args.batch_root).resolve(), args.output_dir_name))


if __name__ == "__main__":
    main()
