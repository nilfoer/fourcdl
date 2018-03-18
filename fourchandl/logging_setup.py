import os.path
import logging
import logging.config
# from logging.handlers import RotatingFileHandler

# logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

# # create a file handler
# # handler = TimedRotatingFileHandler("gwaripper.log", "D", encoding="UTF-8", backupCount=10)
# # max 1MB and keep 5 files
# handler = RotatingFileHandler(os.path.join(ROOTDIR, "fourchandl.log"),
#                               maxBytes=1048576, backupCount=5, encoding="UTF-8")
# handler.setLevel(logging.DEBUG)
# 
# # create a logging format
# formatter = logging.Formatter(
#     "%(asctime)-15s - %(name)-9s - %(levelname)-6s - %(message)s")
# # '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# handler.setFormatter(formatter)
# 
# # add the handlers to the logger
# logger.addHandler(handler)
# 
# # create streamhandler
# stdohandler = logging.StreamHandler(sys.stdout)
# stdohandler.setLevel(logging.INFO)
# 
# # create a logging format
# formatterstdo = logging.Formatter(
#     "%(asctime)s - %(levelname)s - %(message)s", "%H:%M:%S")
# stdohandler.setFormatter(formatterstdo)
# logger.addHandler(stdohandler)

def configure_logging(log_path):
    logging.config.dictConfig({
        'version': 1,
        'formatters': {
            'console': {'format': '%(asctime)s - %(levelname)s - %(message)s', 'datefmt': "%H:%M:%S"},
            "file": {"format": "%(asctime)-15s - %(name)-9s - %(levelname)-6s - %(message)s"}
        },
        'handlers': {
            'console': {
                'level': 'INFO',
                'class': 'logging.StreamHandler',
                'formatter': 'console',
                'stream': 'ext://sys.stdout'
            },
            'file': {
                'level': 'DEBUG',
                'class': 'logging.handlers.RotatingFileHandler',
                'formatter': 'file',
                'filename': log_path,
                'maxBytes': 1048576,
                'backupCount': 5,
                "encoding": "UTF-8"
            }
        },
        'loggers': {
        },
        "root": {
                'level': 'DEBUG',
                'handlers': ['console', 'file']
        },
        'disable_existing_loggers': False
    })

# log to dir of package but set actual logging loc to working dir when called as script (done in main)
configure_logging(os.path.join(os.path.dirname(os.path.realpath(__file__)), "fourchandl.log"))
