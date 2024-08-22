from airflow import DAG
from datetime import timedelta, datetime
from airflow.operators.python import PythonOperator
import pandas as pd
import boto3
from airflow.operators.bash import BashOperator
# from utils.constants import AWS_ACCESS_KEY_ID, AWS_ACCESS_KEY
# from utils.constants import AWS_REGION_NAME, AWS_BUCKET_NAME


s3_client = boto3.client('s3',
    aws_access_key_id='AKIA3M7ACWZ464TEASPT',
    aws_secret_access_key='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',
    region_name='ap-southeast-2')

# s3 buckets
target_bucket_name = 'redfintransformzoneyml2'

# url link from - https://www.redfin.com/news/data-center/
url_by_city = 'https://redfin-public-data.s3.us-west-2.amazonaws.com/redfin_market_tracker/us_national_market_tracker.tsv000.gz'

def extract_data(**kwargs):
    print('in the extract func')
    url = kwargs['url']
    df = pd.read_csv(url, compression='gzip', sep='\t')
    now = datetime.now()
    date_now_string = now.strftime("%d%m%Y%H%M%S")
    print("suc 1")
    file_str = 'redfin_data_' + date_now_string
    output_file_path = f"/home/rayyan/airflow/data/output/"+file_str
    output_list = [output_file_path, file_str]
    df.to_csv(f"{output_file_path}.csv", index=False)
    print("suc 2")
    task_instance = kwargs.get('task_instance')
    if task_instance:
        task_instance.xcom_push(key='my_key', value=output_file_path)
        print("yayyy")

    else:
        print("TaskInstance not found")
    return output_list

def transform_data(**kwargs):
    task_instance = kwargs.get('task_instance')
    data = task_instance.xcom_pull(task_ids="tsk_extract_redfin_data")[0]
    if data:
      print( data)
    else:
       print("No data found in XCom for task_id 'tsk_extract_redfin_data'")
       print(data)

    object_key = task_instance.xcom_pull(task_ids="tsk_extract_redfin_data")[1]
    print('in transform 2')

    df = pd.read_csv(f"{data}.csv")
    print(df.head)
    # Remove commas from the 'city' column
    df['city'] = df['city'].str.replace(',', '')
    cols = ['period_begin','period_end','period_duration', 'region_type', 'region_type_id', 'table_id',
    'is_seasonally_adjusted', 'city', 'state', 'state_code', 'property_type', 'property_type_id',
    'median_sale_price', 'median_list_price', 'median_ppsf', 'median_list_ppsf', 'homes_sold',
    'inventory', 'months_of_supply', 'median_dom', 'avg_sale_to_list', 'sold_above_list', 'parent_metro_region_metro_code', 'last_updated']
   
    df = df[cols]
    print(df.head)

   # df = df.dropna()

    #let's change the period_begin and period_end to date time object and extract years and month.
    df['period_begin'] = pd.to_datetime(df['period_begin'])
    df['period_end'] = pd.to_datetime(df['period_end'])

    df["period_begin_in_years"] = df['period_begin'].dt.year
    df["period_end_in_years"] = df['period_end'].dt.year

    df["period_begin_in_months"] = df['period_begin'].dt.month
    df["period_end_in_months"] = df['period_end'].dt.month
    
    #let's map the month number to their respective month name.
    month_dict = {
        "period_begin_in_months": {
            1 : "Jan",
             2 :  "Feb",
             3: "Mar",
             4: "Apr",
             5: "May",
             6: "Jun",
             7: "Jul",
             8: "Aug",
             9: "Sep",
             10: "Oct",
             11: "Nov",
             12: "Dec",
        },
        "period_end_in_months": {
            1 : "Jan",
             2 :  "Feb",
             3: "Mar",
             4: "Apr",
             5: "May",
             6: "Jun",
             7: "Jul",
             8: "Aug",
             9: "Sep",
             10: "Oct",
             11: "Nov",
             12: "Dec"
        }}
    
    df = df.replace(month_dict)
    print('Num of rows:', len(df))
    print('Num of cols:', len(df.columns))
        
    # Convert DataFrame to CSV format
    csv_data = df.to_csv(index=False)
    print('csv format done')
    # Upload CSV to S3
    object_key = f"{object_key}.csv"
    s3_client.put_object(Bucket=target_bucket_name, Key=object_key, Body=csv_data)

def load_raw_Data_To_bucket(**kwargs):
     task_instance = kwargs.get('task_instance')
     data = task_instance.xcom_pull(task_ids="tsk_extract_redfin_data")[0]
     if data:
         print( data)
     else:
       print("No data found in XCom for task_id 'tsk_extract_redfin_data'")
       print(data)

     object_key = task_instance.xcom_pull(task_ids="tsk_extract_redfin_data")[1]
     print('in transform 2')

     s3_client.put_object(Bucket='store-raw-data-yml2', Key=object_key, Body=data)
    

default_args = {
    'owner': 'Rayyan',
    'start_date': datetime(2024, 8, 18)
}


with DAG('redfin_analytics_dag',
        default_args=default_args,
        # schedule_interval = '@weekly',
        catchup=False) as dag:

        extract_redfin_data = PythonOperator(
        task_id= 'tsk_extract_redfin_data',
        python_callable=extract_data,
        op_kwargs={'url': url_by_city},
        provide_context=True,
        do_xcom_push=True,  # Ensure XCom is being pushed

        dag=dag

        )


        transform_redfin_data = PythonOperator(
        task_id= 'tsk_transform_redfin_data',
        python_callable=transform_data,
        provide_context=True,
        dag=dag

        )

#         load_to_s3 = BashOperator(
#         task_id='tsk_load_to_s3',
#         bash_command=(
#         'aws s3 mv /opt/airflow/data/output/redfin_data_20082024111233.csv s3://storerawdatayml --region ap-southeast-2'
#     ),
# )

        load_to_s3 = PythonOperator(
        task_id= 'tsk_load_redfin_data',
        python_callable=load_raw_Data_To_bucket,
        provide_context=True,
        dag=dag
        )

        extract_redfin_data >> transform_redfin_data >> load_to_s3
