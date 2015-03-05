#!/usr/bin/env python
import os
import json
import time
import argparse
import subprocess
import terminal

snapshot_id = '7067f369f7b76f0a3276beb561820a21c9b5204ab60fbd90524560db96d7cb38'
key_name = 'tempkey'


def get_credentials(utoken, atoken, credsfile):
    if utoken is None and atoken is None:
        try:
            creds = json.load(open(credsfile, 'r'))
            utoken = creds['user_token']
            atoken = creds['access_token']
        except:
            print "Can't open credentials file. \n ", \
                "You must provide a user token and a access token at least one time, or a valid credentials file"
            exit(127)
    elif (utoken is not None and atoken is None) or (utoken is None and atoken is not None):
        print "--utoken AND --atoken parameters must be passed together"
        exit(1)
    else:
        with open(credsfile, 'w') as cfile:
            json.dump({'user_token': utoken, 'access_token': atoken}, cfile)
    return utoken, atoken

def generate_ssh_key(key_file):
    subprocess.call(['ssh-keygen','-f', key_file,'-P',''])

def get_public_key(key_file):
    with open(key_file) as f:
        content = f.readlines()[0].rstrip('\n')
    return str(content)

def start_snap(name, snapshot_id, size=None, script=None):
    output = terminal.start_snapshot(snapshot_id, size, None, name, None, script)
    request_id = output['request_id']
    output = terminal.request_progress(request_id)
    state = 'None'
    time.sleep(1)
    while output['status'] != 'success':
        output = terminal.request_progress(request_id)
        if output['state'] != state:
            state = output['state']
            print('(%s)' % state)
        time.sleep(1)
    container_key = output['result']['container_key']
    subdomain = output['result']['subdomain']
    container_ip = output['result']['container_ip']
    return container_key, container_ip, subdomain

def run_on_terminal(cip, user, script):
    try:
        p = subprocess.Popen(
        ['ssh', '-q' ,'-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null', '-i', 'pemfile',
         user + '@' + cip, script], 0, None,  None, None, None)
        p.wait()
        return p.returncode
    except Exception, e:
        return 'Error: [%s]' % e

def get_script(filename):
    try:
        with open(filename) as f:
            data = f.read()
            data.replace('\n',';')
        return data
    except Exception, e:
        print '(%s)' % e
        return None

def send_script(cip, user, script, path=''):
    try:
        p = subprocess.Popen(
        ['scp', script ,'-q' ,'-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null', '-i', 'pemfile',
         '%s@%s:%s' % (user,cip,path)], 0, None,  None, None, None)
        p.wait()
        return p.returncode
    except Exception, e:
        return 'Error: [%s]' % e

def args_sanitizer(args):
    if args.size not in terminal.instance_types()['instance_types']:
        print "Error. Wrong instance type"
        exit(1)
    if (int(args.quantity) < 1 or int(args.quantity) > 100):
        print "Error. Terminal amount out of bounds ( should be in between 1 and 100 )"
        exit(1)
    if args.method not in ('ssh, startup'):
        print "Error. Not a valid method. (use ssh or startup)"
        exit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--size", type=str, default='medium', help="micro, mini, small, medium, xlarge.. etc")
    parser.add_argument("-q", "--quantity", type=int, default=3, help="How many nodes will have your deploy")
    parser.add_argument("-u", "--utoken", type=str, default=None ,help="Your user token")
    parser.add_argument("-a", "--atoken", type=str, default=None, help="Your access token")
    parser.add_argument("-c", "--creds", type=str, default='/etc/creds.json', help="A credentials json file")
    parser.add_argument("-x", "--script", type=str, default=None, help="A script file to be executed in the new Terminals - \
    With ssh method you can also use a binary executable")
    parser.add_argument('-m', "--method", type=str, default='ssh', help="\"ssh\" or \"startup\" script methods")
    parser.add_argument('-n', "--name", type=str, default='Scripted Terminal', help="The name of your Terminal")
    parser.add_argument('-k', "--ssh_key_file", type=str, default=None, help="Use your own ssh key instead of create a new one - \
    Use your private key name")
    parser.description="Utility to start and setup Terminals"
    args = parser.parse_args()
    args_sanitizer(args)

    # Preparing
    if args.method == 'ssh':
        if args.ssh_key_file is None:
            generate_ssh_key(key_name)
        else:
            key_name=args.ssh_key_file
        publicKey=get_public_key('%s.pub' % key_name)
        script=None
    else:
        script=get_script(args.script)

    # Creating terminals
    terminals=[]
    for i in range(args.quantity):
        name = '%s-%s' % (args.name,i)
        container_key, container_ip, subdomain = start_snap(name, snapshot_id, args.size, script)
        terminals.append({'container_key':container_key, 'container_ip':container_ip, 'subdomain':subdomain, 'name':name})
    time.sleep(2) # Prevent race-condition issues

    # Installing stuff by ssh method
    if args.method == 'ssh':
        for i in range(len(terminals)):
            terminal.add_authorized_key_to_terminal(terminals[i]['container_key'],publicKey)
            time.sleep(1)
            send_script(terminals[i]['container_ip'], 'root', script)
            run_on_terminal(terminals[i]['container_ip'], 'user', '/bin/bash /root/%s' % os.path.basename(script))

    # Print results in json format
    print json.loads(terminals)