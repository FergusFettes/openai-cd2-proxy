import logging

logging_level = logging.DEBUG

logger = logging.getLogger()
logger.setLevel(logging_level)

# Output both to the console and to a file
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
fh = logging.FileHandler('/tmp/server-log.txt')
fh.setLevel(logging_level)
fh.setFormatter(formatter)
logger.addHandler(fh)


ch = logging.StreamHandler()
ch.setLevel(logging_level)
ch.setFormatter(formatter)
logger.addHandler(ch)
