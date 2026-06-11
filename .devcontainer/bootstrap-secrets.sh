#!/usr/bin/env bash
# Wire /secrets/secrets.env into every new shell.
# Called once from postCreateCommand — safe to re-run.
SECRETS_FILE="/secrets/secrets.env"
MARKER=". $SECRETS_FILE"
[ -f "$SECRETS_FILE" ] && . "$SECRETS_FILE"
grep -qF "$MARKER" ~/.bashrc  || echo "$MARKER" >> ~/.bashrc
grep -qF "$MARKER" ~/.profile || echo "$MARKER" >> ~/.profile
