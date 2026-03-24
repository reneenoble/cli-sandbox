#!/usr/bin/env bash
# mystery.sh — What does each of these commands do?
# Use: gh copilot explain "<command>" to find out!

# Command 1
find . -name "*.log" -mtime +7 -delete

# Command 2
ps aux | grep python | awk '{print $2}' | xargs kill -9

# Command 3
du -sh * | sort -rh | head -10

# Command 4
tar -czf backup-$(date +%Y%m%d).tar.gz ./data

# Command 5
awk -F: '$3 >= 1000 {print $1, $3}' /etc/passwd | sort -k2 -n

# Command 6
netstat -tulpn | grep LISTEN | awk '{print $4}' | cut -d: -f2 | sort -n

# Command 7
find /var/log -type f -name "*.gz" -exec ls -lh {} \; | sort -k5 -rh

# Command 8
sed -i 's/\r//' *.txt && chmod +x *.sh
