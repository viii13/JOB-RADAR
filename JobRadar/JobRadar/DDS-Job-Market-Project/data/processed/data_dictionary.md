# Important Column Data Dictionary

| Pipeline field | Workbook column | Type | Meaning | Missing | Unique non-null | Examples |
| --- | --- | --- | --- | --- | --- | --- |
| job_id | jobId | int64 | Identifier for a job posting; used to assess duplicate postings. | 0 | 97679 | 270925008041; 270925007584; 270925007492 |
| job_title | title | str | Role title advertised by the employer. | 0 | 55104 | Sr. HR Recruiter (NON IT); Fire And Safety Officer; Opening For Performance Marketing - Chennai |
| company | companyName | str | Employer or hiring organization name. | 4 | 18668 | Orion; Apollo Hospitals International Limited, Ahmedabad; TVS Credit Services Ltd |
| location | location | str | Location associated with the role. | 0 | 10066 | Kolkata(Chinar Park); Gandhinagar, Ahmedabad; Chennai |
| job_description | jobDescription | str | Free-text description of duties, requirements, or role context. | 0 | 80679 | Preferred candidate profile . .; Ensure active Fire Protection System,such as Fire Hydrant system,Fire extinguishers,Fire Alarm smoke detector system,Sprinkler system keep in good condition; MBA Marketing (preferred Tier II or III B- School). <br><br>Experience <br><br> 12+ years exp in Digital Marketing with a focus on performance marketing/ content strategy / campaign management along with team handling experience<br><br>Mobility Experience / development of mobile sites / Apps |
| skills | tagsAndSkills | str | Tags or skills associated with the role; the future skill-demand pipeline will normalize this field. | 571 | 84307 | Communication,Manpower,Staffing,Convincing Power,Hiring,Recruitment,SR,Communication skills; Safety Officer Activities,Fire Protection,Fire Safety,Fire Engineering,Fire Prevention,Safety Management,Fire Management,Hazard Analysis; Performance Marketing,User Acquisition,growth marketing,Paid Marketing,Acquisition,Performance,Usage,Marketing |
| posting_date | jobUploaded | str | Date or timestamp when the posting was uploaded or published. | 0 | 30 | 6 Days Ago; 6 Days Ago; 6 Days Ago |
| experience | experience | str | Required candidate experience level or range. | 2105 | 287 | 2-4 Yrs; 6-11 Yrs; 12-18 Yrs |
| salary | salary | str | Advertised compensation or salary range. | 0 | 1339 | 2-4 Lacs PA; 3-5 Lacs PA; Not disclosed |
| minimum_salary | minimumSalary | float64 | Structured lower salary bound supplied by the source dataset. | 571 | 164 | 200000.0; 300000.0; 0.0 |
| maximum_salary | maximumSalary | float64 | Structured upper salary bound supplied by the source dataset. | 571 | 204 | 400000.0; 500000.0; 0.0 |
| minimum_experience | minimumExperience | float64 | Structured lower experience bound supplied by the source dataset. | 571 | 31 | 2.0; 6.0; 12.0 |
| maximum_experience | maximumExperience | float64 | Structured upper experience bound supplied by the source dataset. | 571 | 33 | 4.0; 11.0; 18.0 |
