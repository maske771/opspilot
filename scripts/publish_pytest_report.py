#!/usr/bin/env python3
"""Publish a pytest JUnit XML report to OpsPilot Test Center."""

import argparse
import json
import os
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


def parse_report(path: Path) -> dict:
    root = ET.parse(path).getroot()
    cases = []
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    total = passed = failed = skipped = errors = 0
    duration_ms = 0
    for suite in suites:
        for case in suite.findall("testcase"):
            total += 1
            status = "passed"
            message = None
            if case.find("failure") is not None:
                status = "failed"
                failed += 1
                node = case.find("failure")
                message = (node.text or "").strip() if node is not None else None
            elif case.find("error") is not None:
                status = "error"
                errors += 1
                node = case.find("error")
                message = (node.text or "").strip() if node is not None else None
            elif case.find("skipped") is not None:
                status = "skipped"
                skipped += 1
            else:
                passed += 1
            duration_ms += int(float(case.attrib.get("time", "0")) * 1000)
            classname = case.attrib.get("classname")
            file_path = classname.split("::")[0] if classname and "::" in classname else classname
            node_id = f"{file_path or ''}::{case.attrib.get('name', 'unknown')}"
            cases.append({
                "node_id": node_id,
                "name": case.attrib.get("name", "unknown"),
                "file_path": file_path,
                "class_name": classname,
                "status": status,
                "duration_ms": int(float(case.attrib.get("time", "0")) * 1000),
                "message": message,
            })
    run_status = "failed" if failed or errors else "passed"
    return {
        "suite": "pytest",
        "commit_sha": os.getenv("GITHUB_SHA"),
        "branch": os.getenv("GITHUB_REF_NAME"),
        "environment": os.getenv("TEST_CENTER_ENV", "local"),
        "status": run_status,
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "errors": errors,
        "duration_ms": duration_ms,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "tests": cases,
    }


def publish(url: str, token: str, payload: dict) -> None:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": "application/json",
        "X-Test-Center-Token": token,
    })
    with urllib.request.urlopen(request, timeout=15) as response:
        print(response.read().decode("utf-8"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("junit_xml", type=Path)
    parser.add_argument("--url", default=os.getenv("TEST_CENTER_URL", "http://localhost:8000/test-center/runs"))
    parser.add_argument("--token", default=os.getenv("TEST_CENTER_INGEST_TOKEN", "opspilot-test-center-dev"))
    args = parser.parse_args()
    publish(args.url, args.token, parse_report(args.junit_xml))
