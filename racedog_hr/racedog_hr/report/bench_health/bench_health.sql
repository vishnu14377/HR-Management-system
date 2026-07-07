select
  emp.name as "Employee:Link/Employee:120",
  emp.employee_name as "Consultant:Data:150",
  emp.deployment_status as "Status:Data:100",
  emp.hotlist as "Hotlist:Data:80",
  emp.primary_skill as "Skill:Data:120",
  datediff(curdate(), emp.bench_start_date) as "Days on Bench:Int:110",
  emp.availability_date as "Available:Date:100",
  emp.marketing_owner as "Marketing Owner:Data:170",
  emp.visa_status as "Visa:Data:90",
  emp.visa_expiry as "Visa Expiry:Date:100"
from `tabEmployee` emp
where emp.status = 'Active'
  and emp.deployment_status in ('On Bench', 'Marketing', 'Rolling-Off')
order by field(emp.hotlist, 'Red', 'Orange', 'Green'),
  datediff(curdate(), emp.bench_start_date) desc
