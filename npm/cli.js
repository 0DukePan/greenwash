#!/usr/bin/env node
/**
 * `npx greenwash` -- runs the Python implementation.
 *
 * This is a shim, not a reimplementation: the detector, the verifier and the
 * report all live in the Python package, and having two implementations of a
 * correctness tool would be a good way to end up with two different answers.
 *
 * It exists because `npx greenwash` is how a lot of people try things, and
 * "install Python first" is a fine answer but a poor first impression. The shim
 * forwards argv and the exit code untouched, so `--enforce` gates a CI job the
 * same way it does from the command line.
 */

"use strict";

const { spawnSync } = require("child_process");

const PYTHONS = process.platform === "win32"
  ? [["py", ["-3"]], ["python", []], ["python3", []]]
  : [["python3", []], ["python", []]];

function findPython() {
  for (const [command, prefix] of PYTHONS) {
    const probe = spawnSync(command, [...prefix, "-c", "import greenwash"], {
      stdio: "ignore",
    });
    if (probe.status === 0) {
      return { command, prefix };
    }
  }
  return null;
}

function anyPython() {
  for (const [command, prefix] of PYTHONS) {
    const probe = spawnSync(command, [...prefix, "--version"], { stdio: "ignore" });
    if (probe.status === 0) {
      return { command, prefix, hasPackage: false };
    }
  }
  return null;
}

const found = findPython();

if (!found) {
  const bare = anyPython();
  const lines = [
    "greenwash: this npm package runs the Python implementation, and it could not find it.",
    "",
  ];
  if (bare) {
    lines.push(
      `  Python is here (${bare.command}) but the greenwash package is not installed for it.`,
      "  Install it with one of:",
      "",
      "    pipx install greenwash",
      "    pip install greenwash",
      ""
    );
  } else {
    lines.push(
      "  No Python interpreter was found on PATH.",
      "  Install Python 3.10 or newer, then:",
      "",
      "    pipx install greenwash",
      ""
    );
  }
  lines.push("  Everything greenwash does is local: no account, no API key, no network.");
  process.stderr.write(lines.join("\n") + "\n");
  process.exit(3); // the same "could not run" code the CLI uses
}

const result = spawnSync(
  found.command,
  [...found.prefix, "-m", "greenwash", ...process.argv.slice(2)],
  { stdio: "inherit" }
);

if (result.error) {
  process.stderr.write(`greenwash: could not run Python (${result.error.message})\n`);
  process.exit(3);
}
process.exit(result.status === null ? 3 : result.status);
