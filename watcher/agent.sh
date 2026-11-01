# Sourced by process_inbox.sh: the one place the watcher talks to a model.
# NOTES_AGENT picks the agent: claude (Claude Code, the default) or codex (the
# OpenAI Codex CLI). Each run gets the least it needs, because it reads text
# from web pages that can contain instructions aimed at it:
#
#   agent_write DIR PROMPT [IMAGE...]   may edit files in DIR and $processed
#   agent_read  DIR PROMPT              may only read; prints its final reply
#
# claude: file tools only (Read, Write, Edit, Glob, Grep): no shell, no web, no
#   MCP, user settings ignored (--restricted). It reads images and PDFs itself.
# codex: Codex has no file-tools-only mode, so it runs its shell inside the OS
#   sandbox: writes confined to DIR and $processed (read-only for agent_read),
#   no network, no web search, none of your Codex config, MCP servers or rules.
#   Unlike claude it can still read files outside the notes folder; see the
#   README. Images are attached up front (-i), since it can't open them itself.
#
# Expects: $processed, $log, and the settings from watcher.env.

AGENT="${NOTES_AGENT:-claude}"
case "$AGENT" in
  claude)
    agent_bin="${CLIP_CLAUDE_BIN:-${CLAUDE_BIN:-}}"
    agent_model="${CLAUDE_MODEL:-}"
    agent_label="${CLAUDE_MODEL:-account default}"
    model_args=(); [ -n "$agent_model" ] && model_args=(--model "$agent_model") ;;
  codex)
    agent_bin="${CODEX_BIN:-}"
    agent_model="${CODEX_MODEL:-}"
    agent_label="codex · ${CODEX_MODEL:-default model}"
    model_args=(); [ -n "$agent_model" ] && model_args=(-m "$agent_model") ;;
  *) agent_bin="" ;;
esac

agent_signed_in() {
  case "$AGENT" in
    claude) [ -n "${CLIP_CLAUDE_BIN:-}" ] || "$agent_bin" auth status 2>/dev/null | grep -q '"loggedIn": *true' ;;
    codex) "$agent_bin" login status >/dev/null 2>&1 ;;
  esac
}

_codex_exec() {   # SANDBOX DIR PROMPT [IMAGE...]
  local sandbox="$1" dir="$2" prompt="$3"; shift 3
  local img=(); for i in "$@"; do img+=(-i "$i"); done
  local extra=(); [ "$sandbox" = workspace-write ] && extra=(--add-dir "$processed")
  printf '%s' "$prompt" | "$agent_bin" exec --skip-git-repo-check --ephemeral --ignore-user-config --ignore-rules \
    -s "$sandbox" -C "$dir" "${extra[@]}" "${model_args[@]}" "${img[@]}" \
    -c approval_policy='"never"' -c sandbox_workspace_write.network_access=false -c web_search='"disabled"' \
    ${CODEX_OUT:+-o "$CODEX_OUT"} -
}

agent_write() {   # DIR PROMPT [IMAGE...]
  local dir="$1" prompt="$2"; shift 2
  case "$AGENT" in
    claude) ( cd "$dir" && "$agent_bin" -p "$prompt" "${model_args[@]}" --restricted --strict-mcp-config \
                --tools "Read,Write,Edit,Glob,Grep" --permission-mode acceptEdits --add-dir "$processed" ) ;;
    codex) _codex_exec workspace-write "$dir" "$prompt" "$@" ;;
  esac
}

agent_read() {   # DIR PROMPT -> final reply on stdout
  local dir="$1" prompt="$2"
  case "$AGENT" in
    claude) ( cd "$dir" && "$agent_bin" -p "$prompt" "${model_args[@]}" --restricted --strict-mcp-config --tools "Read,Glob,Grep" ) ;;
    codex) local out; out="$(mktemp)"
           CODEX_OUT="$out" _codex_exec read-only "$dir" "$prompt" >> "$log" 2>&1
           cat "$out"; rm -f "$out" ;;
  esac
}

# Images a record's header lists (attachments: or images:), for agents that can't open
# files themselves. A PDF scan becomes a PNG of its first page (sips); a
# multi-page PDF is noted in the log, since only that page is attached.
record_images() {   # RECORD.md...
  [ "$AGENT" = codex ] || return 0
  local md f dir tmp="$processed/.agent-images"   # removed at the end of each run
  mkdir -p "$tmp"
  for md in "$@"; do
    dir="$(dirname "$md")"
    # The header only (the body is page text anyone could write), and plain
    # filenames beside the record: never a path, never a dotfile.
    awk 'NR==1 && /^---$/ {h=1; next} h && /^---$/ {exit} h' "$md" \
      | sed -nE '/^(attachments|images):/,/^[^ ]/s/^  - //p' | while read -r f; do
      case "$f" in */*|.*|"") continue ;; esac
      case "$(printf '%s' "$f" | tr 'A-Z' 'a-z')" in
        *.png|*.jpg|*.jpeg|*.gif|*.webp) [ -f "$dir/$f" ] && echo "$dir/$f" ;;
        *.pdf) [ -f "$dir/$f" ] || continue
               sips -s format png "$dir/$f" --out "$tmp/${f%.*}.page1.png" >/dev/null 2>&1 && echo "$tmp/${f%.*}.page1.png"
               pages="$(mdls -raw -name kMDItemNumberOfPages "$dir/$f" 2>/dev/null)"
               [ "${pages:-1}" -gt 1 ] 2>/dev/null && echo "  ! $f has $pages pages; Codex sees only the first" >> "$log" ;;
      esac
    done
  done
}
