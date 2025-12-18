import logging
import sys

def setup_logger(project_name="my_project", log_file="debug.log"):
    """
    Sets up a robust logging configuration that outputs to both 
    the console and a file.
    """
    logger = logging.getLogger(project_name)
    logger.setLevel(logging.DEBUG)

    log_format = (
        '%(asctime)s | %(levelname)-8s | '
        '[%(filename)s:%(lineno)d] | %(name)s | %(message)s'
    )
    
    formatter = logging.Formatter(log_format, datefmt='%Y-%m-%d %H:%M:%S')

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
