#!env python3

# tooling to help unify google calendar and clockify for bulk updates
#
# requires: gcalcli with google calendar api key
# requires: clockify-cli with clockify api key
#
# install:
# brew install gcalcli clockify-cli
#
# 
import subprocess
import argparse
from datetime import datetime, timedelta
import re


def parse_datetime(date_str, time_str):
    return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")

def calculate_duration(start_date, start_time, end_date, end_time):
    start = parse_datetime(start_date, start_time)
    end = parse_datetime(end_date, end_time)

    duration = (end - start).total_seconds() / 3600  # Convert to hours
    return duration

def round_up_to_nearest_15_minutes(duration):
    # Convert the timedelta to total minutes
    total_minutes = int(duration.total_seconds() / 60)

    # Calculate the number of full 15-minute intervals and add an extra 15 minutes if there's any remainder
    #rounded_minutes = ((total_minutes + 1) // 3) * 3
    rounded_minutes = ((total_minutes) // 15) * 15 

    # brute force the minute count up into the next 15 minute block if there were
    # partial minutes used in that block
    added_minutes=0
    if total_minutes % 15 > 0:
        rounded_minutes += 15 
        added_minutes=1

    #print(f"    {total_minutes} rounded minutes {rounded_minutes} added_minutes={added_minutes}")
    # Convert back to timedelta
    #return timedelta(minutes=rounded_minutes).total_seconds()/3600
    return timedelta(minutes=rounded_minutes).total_seconds()/60

#def run_gcalcli_search(query):
def run_gcalcli_search():
    #command = f"gcalcli search {query} --tsv --details all"
    if not args.startdate or not args.enddate:
        previous_week_start, previous_week_end = get_previous_week_start_and_end()
    else:
        previous_week_start = parse_datetime(args.startdate,"00:00")
        previous_week_end   = parse_datetime(args.enddate,"00:00")
    


    print(f"Previous Week Start: {previous_week_start.strftime('%Y-%m-%d')}")
    span_start = previous_week_start.strftime('%Y-%m-%d')
    print(f"Previous Week End:   {previous_week_end.strftime('%Y-%m-%d')}")
    span_end = previous_week_end.strftime('%Y-%m-%d')

    command = f"gcalcli agenda {span_start} {span_end} --tsv --details id --nodeclined"
    print(f"command is {command}")
    result = subprocess.run(command, shell=True, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return None

    return result.stdout

def load_ignore_strings(file_path):
    """Load ignoreable strings from a file."""
    with open(file_path, 'r') as file:
        return [line.strip() for line in file]


def get_previous_week_start_and_end():
    # Get today's date
    today = datetime.now()

    # Calculate the start of the previous week (Monday)
    previous_monday = today - timedelta(days=today.weekday())

    # Calculate the end of the previous week (Sunday)
    previous_sunday = previous_monday + timedelta(days=6)

    return previous_monday, previous_sunday

def run_clockify_task_list():
    command = "clockify-cli task list --project Customer --format '{{.Name}}'"
    result = subprocess.run(command, shell=True, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return None

    return result.stdout.strip().split('\n')

#def main(query):
def main():
    # Get the clockify task list
    clockify_tasks = run_clockify_task_list()

    if not clockify_tasks:
        return

    #gcal_output = run_gcalcli_search(query)
    gcal_output = run_gcalcli_search()

    if not gcal_output:
        return



    lines = gcal_output.strip().split('\n')
    headers = lines[0].strip().split('\t')

    for line in lines[1:]:
        if args.verbose:
            print(f"DEBUG: {line}")

        values = line.strip().split('\t')


        # Mapping columns to their positions
        id_index = headers.index('id')
        title_index = headers.index('title')  # Corrected from summary to title
        start_date_index = headers.index('start_date')
        start_time_index = headers.index('start_time')
        end_date_index = headers.index('end_date')
        end_time_index = headers.index('end_time')


        id = values[id_index]
        title = values[title_index]
        start_date = values[start_date_index]
        start_time = values[start_time_index]
        end_date = values[end_date_index]
        end_time = values[end_time_index]

        # skip if it's a calendar with no start/end time (all-day events)
        if not start_time or not end_time:
            continue

        # skip if it's a calendar entry we want to ignore all the time
        if title in ignore_strings:
            continue

        duration_hours = calculate_duration(start_date, start_time, end_date, end_time)
        duration_timedelta = timedelta(hours=duration_hours)
        duration = round_up_to_nearest_15_minutes(duration_timedelta)

        rounded_end_time = datetime.strptime(f"{start_date} {start_time}", "%Y-%m-%d %H:%M") + timedelta(minutes=(duration))
      

        if args.verbose:
            print(f"DEBUG:    duration_hours {duration_hours}, duration_timedelta {duration_timedelta}, duration {duration} rounded_end_time {rounded_end_time.replace(tzinfo=None)}")

        matched = "no match"
        
        project = "Admin / Internal"
        task = "Internal Meetings"


        for company_name in clockify_tasks:
            result = re.findall('\\b('+company_name+'|'+company_name.replace(" ","")+')\\b', title, flags=re.IGNORECASE)
            if len(result)>0:
                 matched = f"matched company {company_name}"
                 project = "Customer"
                 task    = company_name
                 break
            result = re.findall('\\b('+company_name+'|'+company_name.replace(" ","")+')\\b', title.replace(" ",""), flags=re.IGNORECASE)
            if len(result)>0:
                 matched = f"matched company {company_name}"
                 project = "Customer"
                 task    = company_name
                 break

        if args.verbose:
            print(f"DEBUG:    {matched}, Duration: {duration:.2f}, Title: {title}, Start Date/Time: {start_date} {start_time}, End Date/Time: {end_date} {end_time}")

        print(f"COMMAND: clockify-cli manual \"{project}\"  \"{start_date} {start_time}\" \"{rounded_end_time}\" \"{title}\" --task \"{task}\"")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Calculate the duration of events from gcalcli search output.")
    #parser.add_argument("query", help="The query to pass to gcalcli search")
    parser.add_argument('-s', '--startdate',  help='override start date, default will be the Monday of the week calculated from "today"')
    parser.add_argument('-e', '--enddate',  help='override end date, default will be the Sunday of the week calculated from "today"')
    parser.add_argument('-v', '--verbose', action='store_true', help='increase output verbosity')
    parser.add_argument('-i', '--ignore-file', help='set the file containing list of ignorable calendar titles', default="./ignore_strings.txt")

    args = parser.parse_args()

    ignore_file_path = args.ignore_file
    ignore_strings = load_ignore_strings(ignore_file_path)

    #main(args.query)
    main()
