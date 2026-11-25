# Data Quality Report

**Source workbook:** `C:\Users\aakas\OneDrive\Documents\Semester 3\Data Analysis using Python\DDS-Job-Market-Project\data\raw\indian-job-market-dataset-2025.xlsx`
**Selected sheet:** Sheet1
**Shape:** 97,929 rows × 17 columns

## Workbook sheets

| Sheet | Rows | Columns | Selection score | Detected job fields |
| --- | --- | --- | --- | --- |
| Sheet1 | 97929 | 17 | 26 | job_id, job_title, company, location, job_description, skills, posting_date, experience, salary, minimum_salary, maximum_salary, minimum_experience, maximum_experience |

## Important columns detected

| Pipeline field | Workbook column |
| --- | --- |
| job_id | jobId |
| job_title | title |
| company | companyName |
| location | location |
| job_description | jobDescription |
| skills | tagsAndSkills |
| posting_date | jobUploaded |
| experience | experience |
| salary | salary |
| minimum_salary | minimumSalary |
| maximum_salary | maximumSalary |
| minimum_experience | minimumExperience |
| maximum_experience | maximumExperience |

## Columns, data types, and missing values

| Column | Data type | Missing | Missing % |
| --- | --- | --- | --- |
| title | str | 0 | 0.0 |
| jobId | int64 | 0 | 0.0 |
| currency | str | 0 | 0.0 |
| jobUploaded | str | 0 | 0.0 |
| companyName | str | 4 | 0.0 |
| tagsAndSkills | str | 571 | 0.58 |
| experience | str | 2105 | 2.15 |
| salary | str | 0 | 0.0 |
| location | str | 0 | 0.0 |
| companyId | int64 | 0 | 0.0 |
| ReviewsCount | float64 | 35252 | 36.0 |
| AggregateRating | float64 | 35252 | 36.0 |
| jobDescription | str | 0 | 0.0 |
| minimumSalary | float64 | 571 | 0.58 |
| maximumSalary | float64 | 571 | 0.58 |
| minimumExperience | float64 | 571 | 0.58 |
| maximumExperience | float64 | 571 | 0.58 |

## Duplicate checks

- Duplicate full rows: 247
- Duplicate job IDs (additional occurrences): 250

## Important categorical values (up to 20 values each)

### title

- . Net Developer
- . Net developer PAN India-SP
- ..Customer Relationship Executive
- ..Inside  Sales Executive
- ..Inside Sales - Executive
- ..Inside Sales Executive
- ..Sales Executive
- ..Tele -Sales Executive
- ..Tele Sales Executive
- ..Tele Sales Representative
- ..Telecalling Executive
- .Customer Support Executive..
- .NET & Angular Developer
- .NET + AWS DevOps Engineer
- .NET + Azure + Angular
- .NET + Azure + Angular Professional
- .NET + React + CI/CD + AWS Lambda fn + Oauth 2
- .NET + React JS Professional
- .NET + SPO (SharePoint Online) Professional
- .NET +OpenShift Developer

### companyName

-  Astranova Mobility
-  Crescent Royale Society
-  Etherea Essentia (Yantasiddhi Pvt Ltd)
-  KIMS Alshifa Super Specialty Hospital
-  KIMS Alshifa Super Specialty Hospital 
-  Khoj Information Technology Pvt Ltd
-  Magellanic Cloud
-  N-LABS.AI PRIVATE LIMITED
-  Shyam Dairy (Unit of SBW Udyog Ltd.)
-  TUV Nord Group
-  Vardhman Probuild Pvt. Ltd.
- (TASC)Total Application Software
- .
- 1 Point 1
- 1 Source Bpo
- 1 point 1
- 1%Club
- 123Stores E Commerce
- 13kbs
- 18th Digitech

### location

- Abohar
- Abu Road
- Achalpur
- Achampet
- Adampur, Punjab
- Adilabad
- Adoni
- Adoor
- Agartala
- Agartala, Anantapur, Kurnool
- Agartala, Dharmanagar
- Agartala, Hassan, Sivakasi, Palakkad, Dhanbad
- Agartala, Jabalpur, Central African Republic
- Agartala, Jabalpur, Junagadh
- Agartala, Kolkata, Mumbai (All Areas)
- Agartala, Kolkata, Tinsukia
- Agartala, North Lakhimpur, Barpeta
- Agartala, Puri
- Agartala, Telangana
- Agartala, Tripura

### experience

- 0 Yrs
- 0-1 Yrs
- 0-10 Yrs
- 0-11 Yrs
- 0-12 Yrs
- 0-13 Yrs
- 0-14 Yrs
- 0-15 Yrs
- 0-2 Yrs
- 0-3 Yrs
- 0-4 Yrs
- 0-5 Yrs
- 0-6 Yrs
- 0-7 Yrs
- 0-8 Yrs
- 0-9 Yrs
- 1 Yrs
- 1-10 Yrs
- 1-11 Yrs
- 1-12 Yrs

## Numeric field statistics

| Column | Count | Mean | Std | Min | Median | Max |
| --- | --- | --- | --- | --- | --- | --- |
| jobId | 97929.0 | 206985423051.85724 | 99878601476.77155 | 10125001764 | 250825003714.0 | 311224008927 |
| companyId | 97929.0 | 27846420.59782087 | 49791844.09428957 | 3 | 2892790.0 | 125142239 |
| ReviewsCount | 62677.0 | 14662.5902643713 | 24744.514682071986 | 2.0 | 962.0 | 104449.0 |
| AggregateRating | 62677.0 | 3.6790481356797553 | 0.4840961981269993 | 1.0 | 3.7 | 5.0 |
| minimumSalary | 97358.0 | 198309.2049138232 | 564076.4828153637 | 0.0 | 0.0 | 70000000.0 |
| maximumSalary | 97358.0 | 318609.58084595 | 841733.6203216175 | 0.0 | 0.0 | 95000000.0 |
| minimumExperience | 97358.0 | 3.9577435855296947 | 3.5811960860598933 | 0.0 | 3.0 | 30.0 |
| maximumExperience | 97358.0 | 7.732646521087122 | 4.500160695839153 | 0.0 | 7.0 | 35.0 |

## Job description examples

- Preferred candidate profile . .
- Ensure active Fire Protection System,such as Fire Hydrant system,Fire extinguishers,Fire Alarm smoke detector system,Sprinkler system keep in good condition
- MBA Marketing (preferred Tier II or III B- School). <br><br>Experience <br><br> 12+ years exp in Digital Marketing with a focus on performance marketing/ content strategy / campaign management along with team handling experience<br><br>Mobility Experience / development of mobile sites / Apps

## TagsAndSkills / skills examples

- Communication,Manpower,Staffing,Convincing Power,Hiring,Recruitment,SR,Communication skills
- Safety Officer Activities,Fire Protection,Fire Safety,Fire Engineering,Fire Prevention,Safety Management,Fire Management,Hazard Analysis
- Performance Marketing,User Acquisition,growth marketing,Paid Marketing,Acquisition,Performance,Usage,Marketing

## Posting date / jobUploaded format

- Column: jobUploaded
- Stored data type: str
- Parseable non-null values: 0 of 97,929
- Example stored values:
- 6 Days Ago
- 6 Days Ago
- 6 Days Ago
