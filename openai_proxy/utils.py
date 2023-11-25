import logging

logging_level = logging.INFO

logger = logging.getLogger()
logger.setLevel(logging_level)

# Output to a file
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
fh = logging.FileHandler('/tmp/server-log.txt')
fh.setLevel(logging_level)
fh.setFormatter(formatter)
logger.addHandler(fh)


# Output to stdout
ch = logging.StreamHandler()
ch.setLevel(logging_level)
ch.setFormatter(formatter)
logger.addHandler(ch)


# Now, set the logging level for all loggers, which will include
# library loggers as well.
for logger_name, logger_obj in logging.Logger.manager.loggerDict.items():
    # Check if the logger supports the setLevel method, which is the case
    # for actual Logger objects but not for PlaceHolder objects which
    # can also be present in the loggerDict.
    if isinstance(logger_obj, logging.Logger):
        logger_obj.setLevel(logging_level)
        logger_obj.propagate = False  # If you want to prevent handlers from upper level loggers to handle these logs
