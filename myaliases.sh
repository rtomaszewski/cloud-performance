alias logclean='for i in $(ls log.*.txt) ; do echo $i; mv $i{,.done};  done'
alias logf='ls -1tr log*.txt | tail -1 | xargs cat '
alias loguser='logf | egrep -i "^\[|^test|report|error|warning|evaluation is running" | egrep -v "Server: csperform|debug|to the list of known hosts"
alias logdebug='logf  | egrep -i debug'

alias logkill='kill $(ps | grep python| awk "{ print \$1}"); fg'

