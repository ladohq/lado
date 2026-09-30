#!/usr/bin/env node
"use strict";

const { version } = require("./package.json");

if (process.argv.includes("--version")) {
  console.log(`lado ${version}`);
} else {
  console.log(
    "LADO (Layered Agent Delegation & Orchestration) is in early development.\n" +
      "Follow progress at https://github.com/ladohq/lado",
  );
}
