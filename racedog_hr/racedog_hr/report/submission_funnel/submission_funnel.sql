select
  sub.submitted_by as "Recruiter:Data:200",
  count(*) as "Total:Int:80",
  sum(sub.status = 'Submitted') as "Submitted:Int:100",
  sum(sub.status = 'Under Review') as "Review:Int:90",
  sum(sub.status in ('Interview Scheduled', 'Interview Done')) as "Interview:Int:100",
  sum(sub.status = 'Offer') as "Offer:Int:70",
  sum(sub.status = 'Placed') as "Placed:Int:70",
  sum(sub.status in ('Rejected', 'Withdrawn')) as "Closed:Int:70"
from `tabSubmission` sub
group by sub.submitted_by
order by count(*) desc
