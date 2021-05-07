#!/usr/bin/env python3

import requests
import pdb;

from pprint import pprint
from csv import reader
from datetime import datetime
from dateutil import tz

#this is the api key from clickup
clickup_key = "pk_12840092_3X2WQV98UWG1AO0L7GYYA4UM12S5RAWL"

clickup_lists = {}
clickup_lists['Precursor Projects'] = 73764974 
clickup_lists['Soft Opening Projects'] = 73764975
clickup_lists[ 'Post Opening Projects'] = 73764976

#headers will be same for all API calls
headers = {"Authorization":clickup_key, "Content-Type":"application/json"}

#hardcoding a list ID as it needs it for custom lookup
list_id = str(clickup_lists['Precursor Projects'])

#building url for api call to get custom field id's
url = "https://api.clickup.com/api/v2/list/" + list_id  + "/field"

# sending get request and saving the response as response object
r = requests.get(url = url, headers = headers)

# extracting data in json format
data = r.json()

#fill list with custom field info including the clickup id for the field
custom_fields_info={}
for result in data['fields']:
    if result['name'] == 'Microsoft Project Task Dependency':
        key = 'depend'
    elif result['name'] == 'Microsoft Project Task Duration':
        key = 'duration'
    elif result['name'] == 'Microsoft Project Task ID':
        key = 'ms_id'
    elif result['name'] == 'Microsoft Project Task Resource Name':
        key = 'resource'

    custom_fields_info[key] = {'id' : result['id'], 'name' : result['name']}

pprint(custom_fields_info)

#open up the csv and get all the MS Project tasks
list_id = 0
with open ('ms_project_export.csv', 'r') as read_obj:
    csv_reader = reader(read_obj)
    #ignore header row
    header = next(csv_reader)
    ms_tasks = {}
    old_list_id = list_id = 0
    for row in csv_reader:
        if not row[1]:
            continue
        elif row[1] in clickup_lists:
            list_id = clickup_lists[row[1]]
            continue

        ms_task = {}
        ms_task['ms_id'] = row[0]
        ms_task['name'] = row[1]
        ms_task['duration'] = row[2]
        ms_task['start'] = row[3]
        ms_task['end'] = row[4]
        ms_task['depend'] = row[5]
        ms_task['resource'] = row[6]
        ms_task['list'] = list_id

        #do all the timezone conversations for start and due dates
        utc_zone = tz.gettz('UTC')
        west_zone = tz.gettz('America/Los_Angeles')

        ms_start_dt = datetime.strptime(ms_task['start'], '%Y-%m-%dT%H:%M:%S')
        west_time = ms_start_dt.replace(tzinfo=west_zone)

        utc = west_time.astimezone(utc_zone)
        ms_task['start'] = int(datetime.timestamp(utc)*1000)

        ms_end_dt = datetime.strptime(ms_task['end'], '%Y-%m-%dT%H:%M:%S')
        west_time = ms_end_dt.replace(tzinfo=west_zone)

        utc = west_time.astimezone(utc_zone)
        ms_task['end'] = int(datetime.timestamp(utc)*1000)

        ms_tasks[ms_task['ms_id']] = ms_task

        
#fetch all the clickup tasks in the relevant lists via the API
cu_tasks = {}
total_counter = 0
#clickup only returns 100 results per call, therefore call it multiple times
#with different page numbers
for page_num in range(0, 100):
    page_counter = 0
    #iterate over all the lists that are relevant
    for list_name in clickup_lists:
        #build URL for the api call to find tasks within list
        url = ("https://api.clickup.com/api/v2/list/" +
               str(clickup_lists[list_name])  + "/task")
        # sending get request and saving the response as response object
        params = {'subtasks':1,
                  'page':page_num}
        
        r = requests.get(url = url,
                         params = params,
                         headers = headers)
        
        # extracting data in json format
        data = r.json()

        #loop over all the tasks for this list and page number
        for result in data['tasks']:
            total_counter += 1;
            page_counter += 1
            cu_task = {}
            cu_task['cu_id'] = result['id']
            cu_task['name'] = result['name']
            cu_task['start'] = int(result['start_date'])
            cu_task['end'] = int(result['due_date'])
            cu_task['list'] = result['list']['id']

            #set all the custom fields
            cu_task['depend'] = ''
            cu_task['duration'] = ''
            cu_task['ms_id'] = ''
            cu_task['resource'] = ''
            for custom_field in result['custom_fields']:
                if 'value' in custom_field:
                    if custom_field['name'] == custom_fields_info['depend']['name']:
                        cu_task['depend'] = custom_field['value']                
                    elif custom_field['name'] == custom_fields_info['duration']['name']:
                        cu_task['duration'] = custom_field['value']                
                    elif custom_field['name'] == custom_fields_info['ms_id']['name']:
                        cu_task['ms_id'] = custom_field['value']
                    elif custom_field['name'] == custom_fields_info['resource']['name']:
                        cu_task['resource'] = custom_field['value']
            #put in a dictionary for later looping
            if 'ms_id' in cu_task:
                cu_tasks[cu_task['ms_id']] = cu_task

    if (page_counter > 0):
        continue

    break
#initialize dictionaries for the different API actions                                
creates = {}
updates = {}
do_nothings = {}
for ms_id in sorted(ms_tasks):
    ms_task = ms_tasks[ms_id]
    if ms_id in cu_tasks:
        cu_task = cu_tasks[ms_id]
        diffs = []
        if ms_task['name'] != cu_task['name']:
            diffs.append('name')
        if ms_task['start'] != cu_task['start']:
            diffs.append('start')
        if ms_task['end'] != cu_task['end']:
            diffs.append('end')
        if ms_task['duration'] != cu_task['duration']:
            diffs.append('duration')
        if ms_task['depend'] != cu_task['depend']:
            diffs.append('depend')
        if ms_task['resource'] != cu_task['resource']:
            diffs.append('resource')
        if str(ms_task['list']) != str(cu_task['list']):
            diffs.append('list')
        #if any fields are different, build our data string for the API call
        if diffs:
            data = """
            {
              "name": "%s",
              "due_date": %s,
              "due_date_time": true,
              "start_date": %s,
              "start_date_time": true,
              "notify_all": false,
              "custom_fields": [
                {
                  "id": "%s",
                  "value": "%s"
                },
                {
                   "id": "%s",
                   "value": "%s"
                },
                {
                   "id": "%s",
                   "value": "%s"
                },
                {
                  "id": "%s",
                  "value": "%s"
                }
             ]
        }
        """
        #put our tokens in
        data = data % (str(ms_task['name']),
                       str(ms_task['end']),
                       str(ms_task['start']),
                       str(custom_fields_info['ms_id']['id']),
                       str(ms_task['ms_id']),
                       str(custom_fields_info['depend']['id']),
                       str(ms_task['depend']),
                       str(custom_fields_info['duration']['id']),
                       str(ms_task['duration']),
                       str(custom_fields_info['resource']['id']),
                       str(ms_task['resource']))                               


            clickup_list = ms_task["list"]
            #build url for the update API call
            url = ("https://api.clickup.com/api/v2/task/" + str(ms_task["list"]) + "/task" +
                   cu_tasks['cu_id'])

            #stick it in a dictionary for creating below
            updates[ms_task['ms_id']] = ({"data":data,"url":url,
                                          "ms_task":ms_task,
                                          "cu_task":cu_task})

        else:
            #the clickup task is the same as the MS Project task, nothing to be done
            do_nothings[ms_task['ms_id']] = ms_task
    else:        
        #create body for API task create
        data = """
        {
          "name": "%s",
          "status": "to do",
          "due_date": %s,
          "due_date_time": true,
          "start_date": %s,
          "start_date_time": true,
          "notify_all": false,
          "custom_fields": [
            {
              "id": "%s",
              "value": "%s"
            },
            {
              "id": "%s",
              "value": "%s"
            },
            {
              "id": "%s",
              "value": "%s"
            },
            {
              "id": "%s",
              "value": "%s"
            }
          ]
        }
        """
        #put our tokens in
        data = data % (str(ms_task['name']),
                       str(ms_task['end']),
                       str(ms_task['start']),
                       str(custom_fields_info['ms_id']['id']),
                       str(ms_task['ms_id']),
                       str(custom_fields_info['depend']['id']),
                       str(ms_task['depend']),
                       str(custom_fields_info['duration']['id']),
                       str(ms_task['duration']),
                       str(custom_fields_info['resource']['id']),
                       str(ms_task['resource']))                               

        clickup_list = ms_task["list"]
        #build URL for API call
        url = "https://api.clickup.com/api/v2/list/" + str(ms_task["list"]) + "/task"

        #add to the dictionary of ms_tasks to create in clickup
        creates.append({"data":data,"url":url,"ms_task":ms_task})

print("ms tasks count " + str(len(ms_tasks.keys())))
print("cu tasks count " + str(len(cu_tasks.keys())))
print("create tasks count " + str(len(creates.keys())))
print("update tasks count " + str(len(updates.keys())))
print("do nothing  tasks count " + str(len(do_nothings.keys())))

#loop over all our creates and call API
#fix me, do we need to worry about exceding rate limit?
for post_data in creates:
    r = requests.post(post_data['url'], post_data['data'], headers=headers)
#loop over all our updates and call API
#fix me, do we need to worry about exceding rate limit?
for post_data in updates:
    #print("MS Project ID " + str(ms_id) + " is different than Clickup ")
    #DO API CALL FOR UPDATING
    r = requests.post(post_data['url'], post_data['data'], headers=headers)

#for ms_task in do_nothings:
    #probably don't need to do anything
    #print("MS Project ID " + str(ms_id) + " matches Clickup ")
