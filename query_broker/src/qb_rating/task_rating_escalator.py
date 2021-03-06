#!/usr/bin/env python
# coding: utf-8
'''
Usage:
    process_task.py <config_file>
    process_task.py (--help|--version)

Arguments:
    config_file     the path of config_file

Options:
    -h --help       show this help message and exit
    -v --version    show version and exit
'''
import time
import sys
import os
import json
import shutil
import docopt
from schema import Schema, SchemaError
import traceback
import dbpc
import rating_global_vars as gv
from task_rating import Worker
from kombu import Connection
from rating_util import *
from logging.handlers import SysLogHandler
import MySQLdb
import statsd
import random


def get_conf_abspath(args):
    os.chdir(gv.run_dir)
    conf_path = args['<config_file>']
    conf_abs_path = os.path.abspath(conf_path)
    os.chdir(gv.bin_dir)
    return conf_abs_path


def check_conf_validation(cf):
    try:
        Schema(lambda x: os.path.exists(x),
               error='config file should exists').validate(cf)
    except SchemaError as e:
        exit(e)


def parse_conf_file(cfg_file):
    with open(cfg_file) as f:
        return json.load(f)


def get_global_vars(cfg):

    cas_cfg = cfg['casmq']
    gv.cas_url = cas_cfg['url']
    gv.cas_queue = cas_cfg['queue']
    gv.cas_exchange = cas_cfg['exchange']
    gv.cas_routing_key = cas_cfg['routing_key']
    #gv.priority = cas_cfg['priority']

    dbpc_cfg = cfg['dbpc']
    gv.dbpc_host = dbpc_cfg['host']
    gv.dbpc_port = dbpc_cfg['port']
    
    gv.dppc_service = dbpc_cfg['service']
    '''
    gv.component = dbpc_cfg['component']
    '''
    gv.interval = dbpc_cfg['interval']
    #gv.try_times_limit = dbpc_cfg['try_times_limit']
    gv.dp = dbpc.dbpc(gv.dbpc_host,
                      int(gv.dbpc_port),
                      gv.dppc_service,
                      "query_broker.qb_rating",
                      int(gv.interval))
    '''
    swift_cfg = cfg['swift']
    gv.st_auth = swift_cfg['ST_AUTH']
    gv.st_user = swift_cfg['ST_USER']
    gv.st_key = swift_cfg['ST_KEY']
    '''
    taskpriorit_cfg = cfg['taskprioritymq']
    gv.taskpriorit_url = taskpriorit_cfg['url']
    gv.taskpriorit_queue = taskpriorit_cfg['queue']
    gv.taskpriorit_exchange = taskpriorit_cfg['exchange']
    gv.taskpriorit_routing_key = taskpriorit_cfg['routing_key']

    gv.databases = cfg['mysql']

    gv.file_ext_list = cfg['filter']['file_ext']
    gv.min_file_size = cfg['filter']['minfilesize']
    gv.max_file_size = cfg['filter']['maxfilesize']

    gv.suspicious_mime_types = cfg['filter']['suspicious_mime_types']

    statsd_cfg = cfg['statsdserver']

    gv.statsdhost = statsd_cfg['host']
    gv.statsdport = statsd_cfg['port']

    gv.score = cfg['filter']['score']
    gv.video_rating_url = cfg['video_rating']

def init_statsd():
    gv.statsd_conn = statsd.client.StatsClient(
        host=gv.statsdhost, port=gv.statsdport)


def init_logger(cf):
    #log_level_map = {'ERROR': 40, 'WARN': 30, 'INFO': 20, 'DEBUG': 10}
    #module = cf['module']
    log_level = cf['log']['level']
    if cf['log'].has_key('logfile'):
        gv.log_file = cf['log']['logfile']
        g_logger.init_logger(
            "query_broker#qb_rating", log_level, gv.log_file, SysLogHandler.LOG_LOCAL2)
        g_logger_info.init_logger(
            "query_broker#qb_rating", log_level, gv.log_file, SysLogHandler.LOG_LOCAL1)
    else:
        g_logger.init_logger(
            "query_broker#qb_rating", log_level, 'syslog', SysLogHandler.LOG_LOCAL2)
        g_logger_info.init_logger(
            "query_broker#qb_rating", log_level, 'syslog', SysLogHandler.LOG_LOCAL1)

def main():
    args = docopt.docopt(__doc__, version=gv.version)
    cfg_file = get_conf_abspath(args)
    check_conf_validation(cfg_file)
    cfg = parse_conf_file(cfg_file)
    init_logger(cfg)
    get_global_vars(cfg)
    init_statsd()
    gv.dp.start()
    while True:
        with Connection(gv.taskpriorit_url) as conn:
            try:
                worker = Worker(
                    conn, gv.taskpriorit_exchange, gv.taskpriorit_queue, gv.taskpriorit_routing_key)
                g_logger.info(trans2json('task priority escalator start'))
                worker.run()
            except Exception:
                g_logger.error(
                    trans2json("task priority escalator %s happend!" % str(traceback.format_exc())))
    gv.dp.join()
if __name__ == '__main__':
    main()
