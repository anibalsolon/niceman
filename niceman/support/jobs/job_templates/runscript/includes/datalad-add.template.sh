{# Send stdout/stderr to /dev/null because this stdin/stdout is dumped to files
   in .niceman and we don't want to change the content mid-add.  Note that we
   don't bother adding .niceman in a separate step because it may be added if
   the leading path includes a hidden directory.
#}

echo "Using DataLad version $(datalad --version)"  # for debugging
{% if message is defined %}
msg={{ shlex_quote(message) }}
{% else %}
msg="[NICEMAN] save results for {{ jobid }}"
{% endif %}
datalad add -m"$msg" . .niceman >/dev/null 2>&1