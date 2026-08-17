# stage_translate.awk — shared stderr->stage translator for runner wrappers.
#
# Rewrites tool stderr lines into the existing stdout stage protocol:
# every input line is passed through to stderr unchanged, and lines matching
# a family's pattern file emit "REVODESIGN_STAGE:<marker>" on stdout.
#
# Usage:  tool ... 2> >(awk -f /app/revocompute/stage_translate.awk \
#                       -v PATTERNS=/app/revocompute/<family>.stages >&1)
#
# Pattern file format: "marker:regex" per line; # comments and blank lines
# ignored. Regexes are awk extended regexes (no ":" in patterns).

BEGIN {
  while ((getline line < PATTERNS) > 0) {
    sub(/^[ \t]*/, "", line)
    if (line == "" || line ~ /^#/) continue
    colon = index(line, ":")
    if (colon == 0) continue
    n += 1
    markers[n] = substr(line, 1, colon - 1)
    regexes[n] = substr(line, colon + 1)
  }
  close(PATTERNS)
}

{
  print > "/dev/stderr"
  for (i = 1; i <= n; i += 1)
    if ($0 ~ regexes[i]) {
      print "REVODESIGN_STAGE:" markers[i]
      fflush()
    }
}
