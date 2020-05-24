#!/bin/env python3
################################################################
# nasxplorer.py
# ---------------
# Simple CIFS shares explorer.
# Input is a JSON file in the following format:
# {
#   "sourceIp": "A.B.C.D",
#   "hostname": "hostname",
#   "username": "username",
#   "password": "password",
#   "domain": "domain_name",
#   "include": ["share_1","share_2"],
#   "exclude": ["share_3","share_4"],
#   "log_level": "DEBUG"
# }
#
# Yaniv Shulman, 2019
################################################################

import sys
import os
import logging
import json
import xlsxwriter

from prettytable import PrettyTable
from smb.SMBConnection import SMBConnection, OperationFailure
from time import ctime
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

# Define input information
ALL_INPUT_PARAMS = ['sourceIp', 'username', 'hostname', 'password', 'domain', 'include', 'exclude', 'log_level']
REQUIRED_INPUT_PARAMS = ['sourceIp', 'hostname', 'username', 'password', 'include', 'exclude']
THRESHOLD = {'last': 0, 'last_24_hours': 1, 'last_7_days': 2, 'last_month': 3, 'last_3_months': 4, 'last_12_months': 5}
DEFAULT_LOG_LEVEL = logging.WARNING


# Return logger with a default level
def get_logger():
    logger = logging.getLogger()
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(DEFAULT_LOG_LEVEL)
    return logger


# Read input parameters from a given JSON file
def get_input_details(filename):
    valid_input = True
    with open(filename) as f:
        try:
            data = json.load(f)
            for param in ALL_INPUT_PARAMS:  # Check validity and if all required parameters exists
                if param not in data.keys() or (param in REQUIRED_INPUT_PARAMS and data[param] == ""):
                    logger.error("Missing input parameter: " + param)
                    valid_input = False
                    break
            if valid_input:
                result = data
            else:
                result = None
        except json.decoder.JSONDecodeError:
            result = None
    return result


# Output summary to XLSX file
def create_excel(table, file_name, path):
    full_path = path + "/" + file_name + ".xlsx"
    if os.path.exists(full_path):
        os.remove(full_path)
    # Create a new Excel file and add a worksheet
    workbook = xlsxwriter.Workbook(full_path)
    worksheet = workbook.add_worksheet()

    # Write column headers
    column_idx = 0
    for field in table.field_names:
        worksheet.write(0, column_idx, field)
        column_idx += 1

    # Fill rows
    row_idx = 1
    for row in table:
        # Write some numbers, with row/column notation.
        column_idx = 0
        for val in row._rows[0]:
            worksheet.write(row_idx,column_idx,val)
            column_idx += 1
        row_idx += 1
    workbook.close()


# Output summary in an ASCII format
def get_table( data):
    headers = ["Share", "Folders", "Files", "Size (GB)", "Last Access", "Accessed (24hrs)", "Accessed (week)",
               "Accessed (month)", "Accessed (3 months)", "Accessed (year)", "Last Modify", "Modified (24hrs)",
               "Modified (week)", "Modified (month)", "Modified (3 months)", "Modified (year)", "Size<100KB",
               "100KB<Size<1MB", "1MB<Size<1GB", "Size>1GB", "Top Types"]
    table = PrettyTable(headers)
    for share in data:
        row = []
        row.append(share)
        row.append(data[share]["folders"])
        row.append(data[share]["files"])
        row.append(data[share]["size"])
        try:
            row.append(ctime(float(data[share]["last_accessed"]["last"])))
        except:
            row.append("")
        row.append(data[share]["last_accessed"]["last_24_hours"])
        row.append(data[share]["last_accessed"]["last_7_days"])
        row.append(data[share]["last_accessed"]["last_month"])
        row.append(data[share]["last_accessed"]["last_3_months"])
        row.append(data[share]["last_accessed"]["last_12_months"])
        try:
            row.append(ctime(float(data[share]["last_written"]["last"])))
        except:
            row.append("")
        row.append(data[share]["last_written"]["last_24_hours"])
        row.append(data[share]["last_written"]["last_7_days"])
        row.append(data[share]["last_written"]["last_month"])
        row.append(data[share]["last_written"]["last_3_months"])
        row.append(data[share]["last_written"]["last_12_months"])
        row.append(data[share]["files_100KB"])
        row.append(data[share]["files_1MB"])
        row.append(data[share]["files_1GB"])
        row.append(data[share]["files_bigger_than_1GB"])
        row.append(data[share]["top_types"])
        table.add_row(row)
    return table


# Return a dict with number of files per size threshold
def breakdown_sizes( list):
    threshold_1 = 100 * 1024  # 100KB
    threshold_2 = 1024 * 1024  # 1MB
    threshold_3 = 1024 * 1024 * 1024  # 1GB

    result = {'threshold_1': 0, 'threshold_2': 0, 'threshold_3': 0, 'threshold_4': 0}
    for item in list:
        if item <= threshold_1: # files <= 100KB
            result['threshold_1'] += 1
        elif threshold_1 < item <= threshold_2:  # 100MB < files <= 1MB
            result['threshold_2'] += 1
        elif threshold_2 < item <= threshold_3:  # 1MB < files <= 1GB
            result['threshold_3'] += 1
        else:  # files > 1GB
            result['threshold_4'] += 1
    return result


# Return a dict with number of files accessed in a given period
def breakdown_access( list):
    # Define time periods
    result_dict = dict.fromkeys(THRESHOLD.keys(), 0)

    list.sort(reverse=True)  # Sort the access list based on last access time
    if len(list) > 0:
        try:
            result_dict['last'] = list[0]
        except:
            result_dict['last'] = ""

        for time in list:
            dt = datetime.utcfromtimestamp(time)
            if dt.date() >= (date.today() - relativedelta(hours=+24)):
                result_dict['last_24_hours'] += 1
                continue
            if dt.date() >= (date.today() - relativedelta(days=+7)):
                result_dict['last_7_days'] += 1
                continue
            if dt.date() >= (date.today() - relativedelta(months=+1)):
                result_dict['last_month'] += 1
                continue
            if dt.date() >= (date.today() - relativedelta(months=+3)):
                result_dict['last_3_months'] += 1
                continue
            if dt.date() >= (date.today() - relativedelta(months=+12)):
                result_dict['last_12_months'] += 1
                continue
    else:
        # Put an empty string for all dict's keys
        result_dict = dict.fromkeys(THRESHOLD.keys(), "")

    return result_dict


# Update the 'types' list with the 'filename' type
def update_type(filename, types):
    # Extract file type
    if len(filename.rsplit('.', 1)) > 1:  # Type is not empty
        filetype = filename.rsplit('.', 1)[1].lower()
    else:
        filetype = ' '

    if filetype in types.keys():  # Type exists in types list
        types[filetype] += 1
    else:
        types[filetype] = 1
    return types


# Returns a list of the 'top' available file types in the share folder
def get_top_types(list, top):
    # Sort the list of file types according to number of occurrences
    list = sorted(list.items(), reverse=True, key=lambda x: x[1])
    top_types = []  # List of 'top' files types ('top' is an argument to the function)
    if len(list) < top:  # Take all types if requested 'top' is bigger than available types
        for type in list:
            top_types.append(type[0])
    else:
        for index in range(top):
            top_types.append(list[index - 1][0])
    return top_types


# Returns a list of shares to scan
def get_shares(share_list, include_list, exclude_list):
    if include_list == []:
        result = []
        # Remove from scan irrelevant and excluded shares
        for share in share_list:
            if (share.name not in exclude_list) and (share.name[len(share.name)-1] != '$'):
                result.append(share.name)
    else:
        result = include_list
    return result


# Extract current folder's name
def get_current_folder(root_folder):
    if len(root_folder.split('\\')) < 5:  # First level under a given share
        result = '/'
    else:
        result = root_folder.split('\\')  # Nested folder within a share
        del result[1:4]
        result = ('/'.join(result)).strip()
    return result


def get_share_content(smb_conn, share_name, folder_path, data):
    try:
        files_list = smb_conn.listPath(share_name, folder_path)
        for y in files_list:
            full_path = share_name + os.path.join(folder_path, y.filename)
            if y.isDirectory:
                if y.filename != "." and y.filename != "..":
                    data['folders'] += 1
                    logger.debug("Now processing folder: [%s]" % full_path)
                    get_share_content(smb_conn, share_name, os.path.join(folder_path,y.filename), data)
            else:
                # Get file details (access, size and type)
                try:
                    data['size'] += y.file_size / 1024 / 1024 / 1024
                    data['files'] += 1
                    data['last_accessed'].append(y.last_access_time)
                    data['last_write'].append(y.last_write_time)
                    data['file_sizes'].append(y.file_size)
                    data['types'] = update_type(y.filename, data['types'])
                except OperationFailure:
                    logger.error(full_path + ": Failed to get attributes")
    except OperationFailure:
        logger.error(share_name + folder_path + ": Unable to open directory")


if __name__ == "__main__":
    logger = get_logger()
    # Input file validations
    if len(sys.argv) != 2:
        logger.error("Please provide a valid input file.")
    else:
        input = get_input_details(sys.argv[1])
        if input == None:
            logger.error("Input file is not valid")
        else:
            try:  # Set log level
                logger.setLevel(input['log_level'])
            except ValueError:
                logger.warning("[%s] is not a valid log level. Using default [%s]" % (input['log_level'], logger.level))

            source_hostname = input['hostname']
            conn = SMBConnection(input['username'], input['password'], '', source_hostname, domain=input['domain'])
            conn.connect(input['sourceIp'])
            # Get a list of shares to analyze
            shares = get_shares(conn.listShares(), input['include'], input['exclude'])
#                data = []  # The analyzed shares data
            data = {}

            for share in shares:
                files_num = 0  # Number of files in a share
                dirs_num = 0  # Number of folders in a share
                size = 0  # Size of a share
                last_accessed_list = []  # Access details of a share
                last_write_list = []  # Write details of a share
                size_list = []  # Sizes files in a share
                type_list = {}  # Type of files in a share
                # Walk on the share's tree
                content_data = {'folders': 0, 'files': 0, 'size': 0, 'last_accessed': [], 'last_write': [],
                                'file_sizes': [], 'types': {}}

                get_share_content( conn, share, os.sep, content_data)

                # Get the top 5 file types in the share
                top_types = get_top_types(content_data['types'], 5)
                # Breakdown access details into thresholds
                access_details = breakdown_access(content_data['last_accessed'])
                write_details = breakdown_access(content_data['last_write'])
                # Break file sizes into thresholds
                size_breakdown = breakdown_sizes(content_data['file_sizes'])

                # Add share's details into the table
                data[share] = dict(folders=content_data['folders'], files=content_data['files'],
                                   size=round(content_data['size'], 2), last_accessed=access_details,
                                   last_written=write_details, files_100KB=size_breakdown['threshold_1'],
                                   files_1MB=size_breakdown['threshold_2'], files_1GB=size_breakdown['threshold_3'],
                                   files_bigger_than_1GB=size_breakdown['threshold_4'],
                                   top_types=(', '.join(top_types)).strip())

            # Output shares details to the console and into a JSON file
            full_path = "./" + source_hostname + ".json"
            with open(full_path, 'w') as json_file:
                json.dump(data, json_file)
            table = get_table(data)
            print( table)
            print("Completed successfully, check out " + full_path)
#                create_excel(table, source_hostname, ".")

