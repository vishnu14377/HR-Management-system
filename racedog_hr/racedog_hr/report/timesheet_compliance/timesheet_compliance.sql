select
  emp.employee_name as "Consultant:Data:180",
  emp.current_client as "Client:Data:170",
  %(period)s as "Period:Data:90",
  coalesce(ts.status, 'Missing') as "Status:Data:120",
  ts.total_hours as "Hours:Float:80",
  ts.submitted_on as "Submitted:Datetime:160",
  ts.name as "Timesheet:Link/Consultant Timesheet:130"
from `tabEmployee` emp
left join `tabConsultant Timesheet` ts
  on ts.consultant = emp.name and ts.period_month = %(period)s
where emp.status = 'Active'
  and emp.deployment_status = 'Working'
  and emp.current_client is not null
  and emp.current_client != ''
order by
  field(coalesce(ts.status, 'Missing'), 'Missing', 'Rejected', 'Submitted', 'Under Review', 'Approved'),
  emp.current_client,
  emp.employee_name
