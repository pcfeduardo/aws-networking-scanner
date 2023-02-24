#!/usr/bin/env python3

'''
Requeriments:

1. Run:
pip3 install boto3
pip3 install pandas
pip3 install openpyxl
'''

import boto3
import pandas
import argparse
from pprint import pprint as pp
import os
import json
from datetime import datetime

__program__ = 'aws-scanner'
__version__ = 'v1.0.0'

filename = "reports/REPORT"
suffix = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")

# Defining an array
vpc_report = []
resource_name_default = {
            'ResourceName': '-'
        }
subnets = []

# Add value function to add value into column
def add_value(dict_obj, key, value):
    if key not in dict_obj:
        dict_obj[key] = value
    elif isinstance(dict_obj[key], list):
        dict_obj[key].append(value)
    else:
        dict_obj[key] = [dict_obj[key], value]

# Setting calls to boto3
def describe_subnets(vpc_id):
    subnets_arr = []
    client_subnets = boto3.client('ec2')
    response = client_subnets.describe_subnets(
        Filters=[
            {
                'Name': 'vpc-id',
                'Values': [
                    f'{vpc_id}',
                ],
            },
        ],
    )
    for subnet in response['Subnets']:
            subnet_id = subnet['SubnetId']
            subnet_cidr = subnet['CidrBlock']
            subnet_az = subnet['AvailabilityZone']

            subnet_details = {
                f'VpcId': vpc_id,
                f'SubnetId': subnet_id,
                f'SubnetCidrBlock': subnet_cidr,
                f'AvailabilityZone': subnet_az,
                # f'Az': zone
            }
            subnets_arr.append(subnet_details)
            subnets.append(subnet_details)
    return subnets_arr

def describe_dhcp_options(dopt):
    ec2_client = boto3.client('ec2')
    resp = []
    response = ec2_client.describe_dhcp_options(DhcpOptionsIds=[
            f'{dopt}',
        ])
    resp.append(response['DhcpOptions'][0]['DhcpConfigurations'])
    if 'Tags' in response['DhcpOptions'][0]:
        if len(response['DhcpOptions'][0]['Tags']) > 0:
            for tag in response['DhcpOptions'][0]['Tags']:
                if tag['Key'] == 'Name':
                    resource_name = {
                        'ResourceName': tag['Value']
                    }
                    resp.append(resource_name)
                else:
                    resource_name = resource_name_default
                    resp.append(resource_name)
        else:
            resource_name = resource_name_default
            resp.append(resource_name)
    else:
        resource_name = resource_name_default
        resp.append(resource_name)
    return resp

def describe_vpcs():
    ec2_client = boto3.client('ec2')
    transit_gateway_client = boto3.client('ec2')

    # Running describe of VPCs
    describe_vpcs = ec2_client.describe_vpcs()

    # Preparing data
    for vpc in describe_vpcs['Vpcs']:
        vpc_id = vpc['VpcId']
        transit_gateways = transit_gateway_client.describe_transit_gateway_attachments(
            Filters=[
                {
                    'Name': 'resource-id',
                    'Values': [
                        f'{vpc_id}',
                    ]
                },
            ]
        )
        transit_gateway_id = ''
        transit_gateway_attachment_id = ''
        transit_gateway_route_table_id = ''
        transit_gateway_resource_type = ''
        
        if len(transit_gateways['TransitGatewayAttachments']) > 0:
            transit_gateway_id = transit_gateways['TransitGatewayAttachments'][0]['TransitGatewayId']
            transit_gateway_attachment_id = transit_gateways['TransitGatewayAttachments'][0]['TransitGatewayAttachmentId']
            
            if 'TransitGatewayRouteTableId' in transit_gateways['TransitGatewayAttachments'][0]:
                transit_gateway_route_table_id = transit_gateways['TransitGatewayAttachments'][0]['TransitGatewayRouteTableId']
            else:
                transit_gateway_route_table_id = ''
            transit_gateway_resource_type = transit_gateways['TransitGatewayAttachments'][0]['ResourceType']
        
        # subnets = describe_subnets(vpc_id)
        
        # Generating data from all subnets from current VPC and put into array
        describe_subnets(vpc_id)

        dhcp_options_id = vpc['DhcpOptionsId']
        dopt = describe_dhcp_options(dhcp_options_id)
        
        domain_names = dopt[0][0]['Values']
        domain_name = []
        for domain in domain_names:
            domain_name.append(domain['Value'])

        domain_name_servers = dopt[0][1]['Values']
        domain_name_server = []
        for dns in domain_name_servers:
            domain_name_server.append(dns['Value'])

        cidr = []
        cidr_block_association_set = vpc['CidrBlockAssociationSet']
        for cidr_block in cidr_block_association_set:
            cidr.append(cidr_block['CidrBlock'])

        vpc_details = {
            'TransitGatewayId': transit_gateway_id,
            'TransitGatewayAttachmentId': transit_gateway_attachment_id,
            'TransitGatewayRouteTableId': transit_gateway_route_table_id,
            'TransitGatewayResourceType': transit_gateway_resource_type,
            'VpcId': vpc_id,
            'CIDRs': ', '.join(cidr),
            'DhcpOptionsId': vpc['DhcpOptionsId'],
            'DhcpOptionsName': dopt[1]['ResourceName'],
            'Domains': ', '.join(domain_name),
            'DomainNameServers': ', '.join(domain_name_server),
            'OwnerId': vpc['OwnerId']
        }
        vpc_report.append(vpc_details)
    dataframe = pandas.DataFrame(vpc_report)
    return dataframe

def set_profile(profile):
    os.environ["AWS_PROFILE"] = profile
    return True

def get_profile():
    return os.environ.get("AWS_PROFILE")

def get_profiles():
    f = open('accounts.json')
    data = json.loads(f.read())
    f.close()
    return data

def start_scan(file):
    data_vpc = describe_vpcs()
    data_subnets = pandas.DataFrame(subnets)
    profile = get_profile()
    data_vpc.to_excel(file, sheet_name=f'{profile}-vpc', index=False)
    data_subnets.to_excel(file, sheet_name=f'{profile}-subnets', index=False)

def main():
    parser = argparse.ArgumentParser(description='scan vpc and dhcp options of aws account', prog=f'{__program__}')
    parser.add_argument('--profile', '-p', default=None, help='AWS Profile')
    parser.add_argument('--multi', '-m', action='store_true', default=False, help='Load profile list: accounts.json')
    parser.add_argument('--version', '-v', action='version', version=f'%(prog)s {__version__}')
    args = parser.parse_args()

    with pandas.ExcelWriter(f'{filename}_{suffix}.xlsx') as report_file:
        if args.multi == True:
            profiles = get_profiles()
            for profile in profiles['profiles']:
                set_profile(profile)
                start_scan(report_file)
        if args.profile != None:
            set_profile(args.profile)
            start_scan(report_file)
        if args.multi == False and args.profile == None:
            start_scan(report_file)

if __name__ == "__main__":
    main()