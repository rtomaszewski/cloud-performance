alias logclean='for i in $(ls log.*.txt) ; do echo $i; mv $i{,.done};  done'
alias logf='ls -1tr *.txt | tail -1 | xargs cat '
alias loguser='logf  | egrep -i "^\[|^test" | egrep -v "Server: csperform"'
alias logdebug='logf  | egrep -i debug'

