import boto3
import pandas as pd
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

# AWS Cost Explorer client
ce = boto3.client('ce')

# Dates
today = datetime.today()
first_of_this_month = datetime(today.year, today.month, 1)
first_of_last_month = first_of_this_month - timedelta(days=1)
first_of_last_month = first_of_last_month.replace(day=1)
first_of_two_months_ago = first_of_last_month - timedelta(days=1)
first_of_two_months_ago = first_of_two_months_ago.replace(day=1)

last_month_name = first_of_last_month.strftime('%B')
two_months_ago_name = first_of_two_months_ago.strftime('%B')

def get_cost_and_usage(start, end):
    response = ce.get_cost_and_usage(
        TimePeriod={'Start': start, 'End': end},
        Granularity='MONTHLY',
        Metrics=['BlendedCost'],
        GroupBy=[{'Type': 'DIMENSION', 'Key': 'SERVICE'}]
    )
    return response['ResultsByTime'][0]['Groups']

# Get costs for last month and the month before
last_month_costs = get_cost_and_usage(first_of_last_month.strftime('%Y-%m-%d'), first_of_this_month.strftime('%Y-%m-%d'))
two_months_ago_costs = get_cost_and_usage(first_of_two_months_ago.strftime('%Y-%m-%d'), first_of_last_month.strftime('%Y-%m-%d'))

# Convert results to DataFrames
last_month_df = pd.DataFrame([(g['Keys'][0], float(g['Metrics']['BlendedCost']['Amount'])) for g in last_month_costs], columns=['Service', 'Cost'])
two_months_ago_df = pd.DataFrame([(g['Keys'][0], float(g['Metrics']['BlendedCost']['Amount'])) for g in two_months_ago_costs], columns=['Service', 'Cost'])

# Merge DataFrames to calculate percentage difference
merged_df = pd.merge(last_month_df, two_months_ago_df, on='Service', suffixes=('_last_month', '_two_months_ago'))

# Calculate percentage difference, handling division by zero, NaN, and small values
merged_df['percentage_diff'] = (
    ((merged_df['Cost_last_month'] - merged_df['Cost_two_months_ago']) / merged_df['Cost_two_months_ago']) * 100
)

# Replace percentage with NaN for cases where both costs are below 0.01
merged_df.loc[(merged_df['Cost_last_month'] < 0.01) & (merged_df['Cost_two_months_ago'] < 0.01), 'percentage_diff'] = float('nan')

# Sort by cost in descending order
merged_df = merged_df.sort_values(by='Cost_last_month', ascending=False)

# Save the report to a PDF file
report_path = './report.pdf'

# Generate PDF report
doc = SimpleDocTemplate(report_path, pagesize=letter)
elements = []

# AWS styled header
header_text = """
    <para align=center spaceb=3>
        <font size=18 color=darkblue>AWS Cloud Cost Report</font>
        <br/><br/>
        <font size=12 color=darkblue>Generated on {date}</font>
    </para>
    """.format(date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

header = Paragraph(header_text, getSampleStyleSheet()['Normal'])
elements.append(header)

# Create a table data list
table_data = [
    ["Service", f"Cost in {last_month_name} ($)", f"Cost in {two_months_ago_name} ($)", "Percentage Difference (%)"]
]

# Add the data from the DataFrame to the table data
for index, row in merged_df.iterrows():
    table_data.append([row['Service'], f"{row['Cost_last_month']:.2f}", f"{row['Cost_two_months_ago']:.2f}", f"{row['percentage_diff']:.2f}" if not pd.isnull(row['percentage_diff']) else "NaN"])

# Create a Table and set its style
table = Table(table_data)
table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, 0), 12),
    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
    ('GRID', (0, 0), (-1, -1), 1, colors.black)
]))

# Add the table to the elements list
elements.append(table)

# Build the PDF
doc.build(elements)

# Print a message indicating the report has been saved
print(f"Report saved to {report_path}")
