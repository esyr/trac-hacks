#!/usr/bin/env python
# -*- coding: utf-8 -*-
#

# if you want to test this script, set this True:
#   then it won't send any mails, just it'll print out the produced html and text
#test = False
test = False

#which kind of db is Trac using?
mysql = False
pgsql = False
sqlite = True

# for mysql/pgsql:
dbhost="localhost"
dbuser="database_user"
dbpwd="database_password"
dbtrac="database_of_trac"
#or for sqlite:
sqlitedb='/path/to/trac/db/trac.db'
#or if your db is in memory:
#sqlitedb=':memory:'

# the url to the trac (notice the slash at the end):
trac_url='https://trac.example.org/path/to/trac/'
# the default domain, where the users reside
#  ie: if no email address is stored for them, username@domain.tld will be used
to_domain="@example.org"

import codecs, sys
sys.setdefaultencoding('utf-8')
import site

# importing the appropriate database connector
#   (you should install one, if you want to use ;)
#    or you can use an uniform layer, like sqlalchemy)
if mysql:
    import MySQLdb
if pgsql:
    import psycopg2
if sqlite:
    from pysqlite2 import dbapi2 as sqlite

import time
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
db = None
cursor = None

try:
    if mysql:
        db = MySQLdb.connect(host=dbhost, user=dbuser, passwd=dbpwd, db=dbtrac)
    if pgsql:
        db = psycopg2.connect("host='"+ dbhost +"' user='" + dbuser + "' password='" + dbpwd + "' dbname='" + dbtrac + "'")
    if sqlite:
        db = sqlite.connect(sqlitedb)
except:
    print "cannot connect to db"
    raise
    sys.exit(1)

cursor = db.cursor()

fields = ['summary', 'component', 'priority', 'status', 'owner', 'reporter']

#I think MySQL needs '"' instead of "'" without any ';',
# with more strict capitalization (doubling quotes mean a single quote ;) )
# so you'll have to put these queries into this format:
# sql="""query""" or sql='"query"' like
# sql = '"SELECT owner FROM ticket WHERE status !=""closed""""'
# for postgresql simply use:
sql = "select id, %s from ticket where status == 'testing' or status == 'pre_testing';" % ', '.join(fields)
cursor.execute(sql)
tickets = cursor.fetchall()
tickets_dict = {}

# Reading last exec time
last_exec_path = '/var/local/trac_testing_tickets_notify_last_exec_timestamp'
last_exec = 0
try:
    f = open(last_exec_path, "r")
    last_exec = int(f.read())
    f.close()
except:
    last_exec = 0

cur_time = int(time.time())
notify_tickets = set()
time_quant = 86400 # seconts per day - frequence of reminds
ticket_url = 'https://trac.example.org/path/to/trac/ticket/'

recipient_list = ['recipient1@example.org', 'recipient2@example.arg', ]

for ticket in tickets:
    tickets_dict[ticket[0]] = {'id': ticket[0]}
    offset = 1
    for field in fields:
        tickets_dict[ticket[0]][field] = ticket[offset]
        offset += 1

    sql = "select time from ticket_change where ticket == %d and field == 'status' and (newvalue == 'testing' or newvalue == 'pre_testing') order by time desc limit 1;" % ticket[0]
    cursor.execute(sql)
    last_time = cursor.fetchall()
    if len(last_time) > 0:
        last_time = last_time[0][0]
        if (int((cur_time - last_time) / time_quant) != int((last_exec - last_time) / time_quant)) and int((cur_time - last_time) / time_quant) > 0:
            notify_tickets |= set([ticket[0], ])

# No new tickets - aborting
if len(notify_tickets) == 0:
    print 'No new tickets: aborting.'
    exit()

#calculating column widths
column_widths = {}
for id in notify_tickets:
    for field, value in tickets_dict[id].iteritems():
        column_widths[field] = field in column_widths and max(column_widths[field], len("%s" % value)) or max(len("%s" % value), len("%s" % field))

#generating mail text
msg_header = """
List of tickets pending your attention:
"""
msg_tail = """
Trac testing tickets notification script.
"""
header_line_template = '|| %%(id)%ds ||' % (len(ticket_url) + column_widths['id'])
normal_line_template = '|| %s%%(id)%ds ||' % (ticket_url, column_widths['id'])
line_template = ''
for field in fields:
    line_template += ' %%(%s)%ds ||' % (field, column_widths[field])

header = { 'id' : 'URL' }
for field in fields:
    header[field] = field
table_header = (header_line_template + line_template) % header

table = []
for id in notify_tickets:
    table.append((normal_line_template + line_template) % tickets_dict[id])

msg = '\n'.join ([msg_header, table_header] + table + [msg_tail])

htmlmsg_header = '''
<html>
    <head>
        <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
    </head>
    <body>
        <table>
'''
htmlmsg_tail = '''
        </table>
    </body>
</html>
'''

normal_line_template = '<td><a href="%s%%(id)s">%%(id)s</a></td>' % ticket_url
line_template = ''
for field in fields:
    line_template += '<td>%%(%s)s</td>' % field

htmltable_header = '<tr><th>' + '</th><th>'.join(['Ticket'] + fields) + '</th></tr>'
htmltable = []
for id in notify_tickets:
    htmltable.append(('<tr>' + normal_line_template + line_template + '</tr>') % tickets_dict[id])

htmlmsg = '\n'.join ([htmlmsg_header, htmltable_header] + htmltable + [htmlmsg_tail])

import email.Charset
email.Charset.add_charset('utf-8', email.Charset.SHORTEST, None, None)

if test:
    print msg
    print
    print htmlmsg
else:
    mailmsg = MIMEMultipart('alternative')
    mailmsg['Subject'] = "Report testing Tickets at %s" % time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(time.time()))
    mailmsg['From'] = 'trac@example.org'
    mailmsg['To'] = ', '.join(recipient_list)

    part1 = MIMEText(msg, 'plain')
    part2 = MIMEText(htmlmsg.encode('utf-8', 'replace'), 'html', 'utf-8')

    mailmsg.attach(part1)
    mailmsg.attach(part2)

    s = smtplib.SMTP()
    s.connect()
    s.sendmail(mailmsg['From'], recipient_list, mailmsg.as_string())
    s.close()

    f = open(last_exec_path, "w")
    f.write("%s" % cur_time)
    f.close()
