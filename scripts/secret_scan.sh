#!/usr/bin/env bash
# Scan the full git history for secrets. Prints counts only, never a matched value.
#   scripts/secret_scan.sh        exit 0 if clean, 1 if anything is found
# Patterns: provider keys (Groq gsk_, Gemini AIza and AQ., OpenRouter sk-or-, OpenAI-style sk-), GitHub,
# Hugging Face, Slack and AWS tokens, private keys; plus every non-empty value in the local .env.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

LOG=$(mktemp)
trap 'rm -f "$LOG"' EXIT
git log -p --all --full-history > "$LOG"
ADDED=$(mktemp)
trap 'rm -f "$LOG" "$ADDED"' EXIT
grep -E '^\+' "$LOG" > "$ADDED" || true

found=0
check() {  # name, extended regex
  local n
  n=$(grep -cE -- "$2" "$ADDED" || true)
  printf '%-28s %s\n' "$1" "$n"
  [ "$n" -eq 0 ] || found=1
}

echo "history: $(git rev-list --all --count) commits, $(wc -c < "$LOG" | tr -d ' ') bytes"
check "groq gsk_"            'gsk_[A-Za-z0-9]{20,}'
check "gemini AIza"          'AIza[0-9A-Za-z_-]{30,}'
check "gemini AQ."           'AQ\.[0-9A-Za-z_-]{20,}'
check "openrouter sk-or-"    'sk-or-[A-Za-z0-9-]{20,}'
check "openai-style sk-"     'sk-[A-Za-z0-9]{20,}'
check "github ghp_/pat"      'ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}'
check "huggingface hf_"      'hf_[A-Za-z0-9]{20,}'
check "slack xox"            'xox[baprs]-[A-Za-z0-9-]{10,}'
check "aws AKIA"             'AKIA[0-9A-Z]{16}'
check "private key"          'BEGIN [A-Z ]*PRIVATE KEY'

# Every secret-like value set in the local .env (names with KEY, TOKEN, SECRET or PASSWORD) must not appear
# anywhere in history. "|| [ -n "$key" ]" keeps a last line that has no trailing newline.
if [ -f .env ]; then
  while IFS='=' read -r key value || [ -n "$key" ]; do
    [[ -z "$key" || "$key" == \#* ]] && continue
    [[ "$key" =~ (KEY|TOKEN|SECRET|PASSWORD) ]] || continue
    value="${value%$'\r'}"; value="${value#\"}"; value="${value%\"}"; value="${value#\'}"; value="${value%\'}"
    [[ ${#value} -lt 8 ]] && continue  # empty or placeholder-short
    n=$(grep -cF -- "$value" "$LOG" || true)
    printf '%-28s %s\n' ".env $key" "$n"
    [ "$n" -eq 0 ] || found=1
  done < <(grep -E '^[A-Z_]+=' .env)
fi

echo "--- .env tracked or ever committed?"
tracked=$(git ls-files --error-unmatch .env 2>/dev/null && echo yes || echo no)
ever=$(git log --all --full-history --oneline -- .env | wc -l | tr -d ' ')
echo "tracked: $tracked, commits touching .env: $ever"
[ "$tracked" = "no" ] && [ "$ever" = "0" ] || found=1

[ "$found" -eq 0 ] && echo "CLEAN" || echo "FOUND SOMETHING"
exit "$found"
