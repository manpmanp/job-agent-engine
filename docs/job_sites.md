<!--
  Job-search agent engine
  File:    docs/job_sites.md
  Purpose: Readable list of job sites by country, generated from engine/defaults/job_sites.json.
  Author:  manpmanp <manp.node@gmail.com>
  Generated with Claude (Anthropic), under the author's direction and review.
  License: MIT (see LICENSE)
  Version: 0.4.3
  Date:    2026-10-29
-->

# Job sites by country

Checked on 2026-10-29 against each country's EURES "How to find a job" page
or other official or primary sources (listed per country). The same data is
in `engine/defaults/job_sites.json`, which the app reads.

How the engine can use a site:

| Access | Meaning |
|---|---|
| built in | Searched automatically by the engine (some need a free key in Settings). |
| API (key) | Has an official API that needs a free key; not built in yet. |
| API (no key) | Has an official API without a key; not built in yet. |
| browse | No automatic search: opened by you or by an agent, read only. |

Postings are only counted as confirmed when they are found on the employer's own site or on one of the sites below.

## International and multi-country

| Site | Type | Access | Note |
|---|---|---|---|
| [EURES (all EU/EEA countries and Switzerland)](https://eures.europa.eu) | public | browse | The EU's job mobility portal; collects public employment service vacancies. |
| [JSearch (Google for Jobs)](https://rapidapi.com) | aggregator | built in | Built in; needs your RapidAPI key. Most countries. |
| [Adzuna](https://developer.adzuna.com) | aggregator | built in | Built in; needs a free key. AT AU BE BR CA CH DE ES FR GB IN IT MX NL NZ PL SG US ZA (not the Nordics). |
| [Hacker News "Who is hiring?"](https://news.ycombinator.com) | aggregator | built in | Built in. Startups, often remote. |
| [Y Combinator startup jobs](https://www.ycombinator.com/jobs) | aggregator | built in | Built in. |
| [Jooble](https://jooble.org/api/about) | aggregator | API (key) | Free API key on request, 60+ countries. Not yet built in. |
| [Careerjet](https://www.careerjet.com/partners) | aggregator | API (key) | Partner API (affiliate ID). Not yet built in. |
| [Remotive (remote jobs)](https://remotive.com/api/remote-jobs) | aggregator | API (no key) | No key; at most 4 requests a day, attribution required. Not yet built in. |
| [LinkedIn Jobs](https://www.linkedin.com/jobs) | private | browse | Read only: never apply, connect or message. |
| [Indeed](https://www.indeed.com/worldwide) | private | browse | Country sites for most countries listed here. |

## Academic and research

| Site | Type | Access | Note |
|---|---|---|---|
| [EURAXESS (Europe, research jobs)](https://euraxess.ec.europa.eu) | academic | browse |  |
| [AcademicPositions (mostly Europe)](https://academicpositions.com) | academic | browse |  |
| [jobs.ac.uk (UK, some international)](https://www.jobs.ac.uk) | academic | browse |  |
| [Times Higher Education Jobs](https://www.timeshighereducation.com) | academic | browse |  |
| [Nature Careers (science)](https://www.nature.com/naturecareers) | academic | browse |  |
| [HigherEdJobs (US)](https://www.higheredjobs.com) | academic | browse |  |
| [Euroscience Jobs (Europe)](https://www.eurosciencejobs.com) | academic | browse |  |
| [academics.com (Germany, Austria, Switzerland)](https://www.academics.com) | academic | browse |  |
| [ABG (France, PhD holders)](https://www.abg.asso.fr/en/candidatOffres) | academic | browse |  |
| [jobRxiv (science)](https://jobrxiv.org) | academic | browse |  |

Sources: <https://www.ox.ac.uk/careers/who-we-support/researchers/getting-a-job/finding-vacancies-for-researchers>

## Nordic

### Denmark (DK)

| Site | Type | Access | Note |
|---|---|---|---|
| [Jobnet](https://jobnet.dk) | public | browse |  |
| [Jobindex](https://www.jobindex.dk) | private | browse | Denmark's largest job site. |
| [Work in Denmark](https://www.workindenmark.dk) | public | browse | Public service for international candidates. |

Sources: <https://eures.europa.eu/living-and-working/living-and-working-conditions-europe/living-and-working-conditions-denmark_en>, <https://www.workindenmark.dk>

### Finland (FI)

| Site | Type | Access | Note |
|---|---|---|---|
| [Työmarkkinatori (Job Market Finland)](https://tyomarkkinatori.fi) | public | browse |  |
| [Duunitori](https://duunitori.fi) | private | browse |  |
| [Oikotie Työpaikat](https://tyopaikat.oikotie.fi) | private | browse |  |

Sources: <https://eures.europa.eu/living-and-working/living-and-working-conditions-europe/living-and-working-conditions-finland_en>

### Iceland (IS)

| Site | Type | Access | Note |
|---|---|---|---|
| [Vinnumálastofnun / EURES Iceland](https://work.iceland.is) | public | browse |  |
| [Alfreð](https://alfred.is) | private | browse |  |

Sources: <https://eures.europa.eu/living-and-working/living-and-working-conditions-europe/living-and-working-conditions-iceland_en>

### Norway (NO)

| Site | Type | Access | Note |
|---|---|---|---|
| [arbeidsplassen.no (NAV)](https://arbeidsplassen.nav.no) | public | API (no key) | NAV job feed API (pam-stilling-feed.nav.no) with a free public token; no server-side filter. Not yet built in. |
| [FINN jobb](https://www.finn.no/job) | private | browse | The largest private board; not in the NAV feed. |

Sources: <https://pam-stilling-feed.nav.no>, <https://eures.europa.eu/living-and-working/living-and-working-conditions-europe/living-and-working-conditions-norway_en>

### Sweden (SE)

| Site | Type | Access | Note |
|---|---|---|---|
| [Platsbanken (Arbetsförmedlingen)](https://arbetsformedlingen.se/platsbanken) | public | built in | Searched automatically through the free JobTech API. |
| [Øresunddirekt (Sweden-Denmark commuting)](https://www.oresunddirekt.se) | public | browse | Guide, not a job board. |

Sources: <https://jobtechdev.se>, <https://eures.europa.eu/living-and-working/living-and-working-conditions-europe/living-and-working-conditions-sweden_en>

## Western Europe

### Austria (AT)

| Site | Type | Access | Note |
|---|---|---|---|
| [AMS alle jobs](https://www.ams.at) | public | browse |  |
| [karriere.at](https://www.karriere.at) | private | browse |  |

Sources: <https://eures.europa.eu/living-and-working/living-and-working-conditions-europe/living-and-working-conditions-austria_en>

### Belgium (BE)

| Site | Type | Access | Note |
|---|---|---|---|
| [VDAB (Flanders)](https://www.vdab.be) | public | browse |  |
| [Le Forem (Wallonia)](https://www.leforem.be) | public | browse |  |
| [Actiris (Brussels)](https://www.actiris.brussels) | public | browse |  |

Sources: <https://eures.europa.eu/living-and-working/living-and-working-conditions-europe/living-and-working-conditions-belgium_en>

### France (FR)

| Site | Type | Access | Note |
|---|---|---|---|
| [France Travail](https://www.francetravail.fr) | public | browse | The public offers API was withdrawn; browse only. |
| [APEC (managers and engineers)](https://www.apec.fr) | private | browse |  |
| [Welcome to the Jungle](https://www.welcometothejungle.com/fr) | private | browse |  |
| [HelloWork](https://www.hellowork.com) | private | browse |  |

Sources: <https://eures.europa.eu/living-and-working/living-and-working-conditions-europe/living-and-working-conditions-france_en>, <https://www.data.gouv.fr>

### Germany (DE)

| Site | Type | Access | Note |
|---|---|---|---|
| [Jobsuche (Bundesagentur für Arbeit)](https://www.arbeitsagentur.de/jobsuche) | public | browse | An unofficial API exists, but its terms restrict reuse, so it is not used. |
| [StepStone](https://www.stepstone.de) | private | browse | The largest private board. |
| [Arbeitnow](https://www.arbeitnow.com) | aggregator | API (no key) | Free job-board API, no key (mostly Germany and remote). Not yet built in. |

Sources: <https://eures.europa.eu/living-and-working/living-and-working-conditions-europe/living-and-working-conditions-germany_en>, <https://www.arbeitnow.com/api/job-board-api>

### Liechtenstein (LI)

| Site | Type | Access | Note |
|---|---|---|---|
| [AMS FL (Labour Market Service)](https://www.amsfl.li) | public | browse |  |

Sources: <https://www.integration.li/en/work/work>

### Luxembourg (LU)

| Site | Type | Access | Note |
|---|---|---|---|
| [ADEM](https://adem.public.lu) | public | browse |  |
| [Moovijob](https://www.moovijob.com) | private | browse |  |
| [jobs.lu](https://www.jobs.lu) | private | browse |  |

Sources: <https://eures.europa.eu/living-and-working/living-and-working-conditions-europe/living-and-working-conditions-luxembourg_en>

### Netherlands (NL)

| Site | Type | Access | Note |
|---|---|---|---|
| [werk.nl (UWV)](https://www.werk.nl) | public | browse |  |
| [Nationale Vacaturebank](https://www.nationalevacaturebank.nl) | private | browse |  |

Sources: <https://eures.europa.eu/living-and-working/living-and-working-conditions-europe/living-and-working-conditions-netherlands_en>

### Switzerland (CH)

| Site | Type | Access | Note |
|---|---|---|---|
| [Job-Room (SECO)](https://www.job-room.ch) | public | browse |  |
| [jobs.ch](https://www.jobs.ch) | private | browse |  |
| [jobup.ch](https://www.jobup.ch) | private | browse | French-speaking Switzerland. |

Sources: <https://eures.europa.eu/living-and-working/living-and-working-conditions-europe/living-and-working-conditions-switzerland_en>

## British Isles

### Ireland (IE)

| Site | Type | Access | Note |
|---|---|---|---|
| [JobsIreland](https://jobsireland.ie) | public | browse |  |
| [IrishJobs](https://www.irishjobs.ie) | private | browse |  |
| [Jobs.ie](https://www.jobs.ie) | private | browse |  |

Sources: <https://eures.europa.eu/living-and-working/living-and-working-conditions-europe/living-and-working-conditions-ireland_en>

### United Kingdom (GB)

| Site | Type | Access | Note |
|---|---|---|---|
| [Find a job (DWP)](https://findajob.dwp.gov.uk) | public | browse |  |
| [Reed](https://www.reed.co.uk) | private | API (key) | Free API key (reed.co.uk/developers). Not yet built in. |
| [Totaljobs](https://www.totaljobs.com) | private | browse |  |
| [CV-Library](https://www.cv-library.co.uk) | private | browse |  |

Sources: <https://eures.europa.eu/living-and-working/living-and-working-conditions-europe/living-and-working-conditions-united-kingdom_en>, <https://www.reed.co.uk/developers>

## Southern Europe

### Cyprus (CY)

| Site | Type | Access | Note |
|---|---|---|---|
| [PES Cyprus](https://www.pescps.dl.mlsi.gov.cy) | public | browse |  |
| [Ergodotisi](https://www.ergodotisi.com) | private | browse |  |

Sources: <https://eures.europa.eu/living-and-working/living-and-working-conditions-europe/living-and-working-conditions-cyprus_en>

### Greece (GR)

| Site | Type | Access | Note |
|---|---|---|---|
| [DYPA](https://www.dypa.gov.gr) | public | browse |  |
| [Kariera.gr](https://www.kariera.gr) | private | browse |  |
| [Skywalker.gr](https://www.skywalker.gr) | private | browse |  |

Sources: <https://eures.europa.eu/living-and-working/living-and-working-conditions-europe/living-and-working-conditions-greece_en>

### Italy (IT)

| Site | Type | Access | Note |
|---|---|---|---|
| [ClicLavoro](https://www.cliclavoro.gov.it) | public | browse |  |
| [InfoJobs Italia](https://www.infojobs.it) | private | browse |  |

Sources: <https://eures.europa.eu/living-and-working/living-and-working-conditions-europe/living-and-working-conditions-italy_en>

### Malta (MT)

| Site | Type | Access | Note |
|---|---|---|---|
| [Jobsplus](https://jobsplus.gov.mt) | public | browse |  |

Sources: <https://eures.europa.eu/living-and-working/living-and-working-conditions-europe/living-and-working-conditions-malta_en>

### Portugal (PT)

| Site | Type | Access | Note |
|---|---|---|---|
| [IEFP Online](https://www.iefp.pt) | public | browse |  |
| [Net-Empregos](https://www.net-empregos.com) | private | browse |  |
| [ITJobs (IT)](https://www.itjobs.pt) | private | browse |  |

Sources: <https://eures.europa.eu/living-and-working/living-and-working-conditions-europe/living-and-working-conditions-portugal_en>

### Spain (ES)

| Site | Type | Access | Note |
|---|---|---|---|
| [Empléate / Sistema Nacional de Empleo](https://www.sistemanacionalempleo.es) | public | browse |  |
| [InfoJobs](https://www.infojobs.net) | private | browse |  |
| [Tecnoempleo (IT and tech)](https://www.tecnoempleo.com) | private | browse |  |

Sources: <https://eures.europa.eu/living-and-working/living-and-working-conditions-europe/living-and-working-conditions-spain_en>

## Central and Eastern Europe

### Bulgaria (BG)

| Site | Type | Access | Note |
|---|---|---|---|
| [Employment Agency](https://www.az.government.bg) | public | browse |  |
| [jobs.bg](https://www.jobs.bg) | private | browse |  |
| [zaplata.bg](https://www.zaplata.bg) | private | browse |  |
| [karieri.bg](https://www.karieri.bg) | private | browse |  |

Sources: <https://eures.europa.eu/living-and-working/living-and-working-conditions-europe/living-and-working-conditions-bulgaria_en>

### Croatia (HR)

| Site | Type | Access | Note |
|---|---|---|---|
| [HZZ job portal](https://burzarada.hzz.hr) | public | browse |  |
| [MojPosao](https://www.moj-posao.net) | private | browse |  |
| [Posao.hr](https://www.posao.hr) | private | browse |  |

Sources: <https://eures.europa.eu/living-and-working/living-and-working-conditions-europe/living-and-working-conditions-croatia_en>

### Czechia (CZ)

| Site | Type | Access | Note |
|---|---|---|---|
| [Úřad práce ČR](https://www.uradprace.cz) | public | browse |  |
| [Jobs.cz](https://www.jobs.cz) | private | browse |  |

Sources: <https://eures.europa.eu/living-and-working/living-and-working-conditions-europe/living-and-working-conditions-czechia_en>

### Hungary (HU)

| Site | Type | Access | Note |
|---|---|---|---|
| [Virtual Labour Market Portal (NFSZ)](https://vmp.munka.hu) | public | browse |  |
| [Profession.hu](https://www.profession.hu) | private | browse |  |

Sources: <https://eures.europa.eu/living-and-working/living-and-working-conditions-europe/living-and-working-conditions-hungary_en>

### Poland (PL)

| Site | Type | Access | Note |
|---|---|---|---|
| [Centralna Baza Ofert Pracy](https://oferty.praca.gov.pl) | public | browse |  |
| [Pracuj.pl](https://www.pracuj.pl) | private | browse |  |
| [Just Join IT (IT)](https://justjoin.it) | private | browse |  |

Sources: <https://eures.europa.eu/living-and-working/living-and-working-conditions-europe/living-and-working-conditions-poland_en>

### Romania (RO)

| Site | Type | Access | Note |
|---|---|---|---|
| [ANOFM](https://www.anofm.ro) | public | browse |  |
| [eJobs](https://www.ejobs.ro) | private | browse |  |
| [BestJobs](https://www.bestjobs.eu) | private | browse |  |
| [Hipo](https://www.hipo.ro) | private | browse |  |

Sources: <https://eures.europa.eu/living-and-working/living-and-working-conditions-europe/living-and-working-conditions-romania_en>

### Slovakia (SK)

| Site | Type | Access | Note |
|---|---|---|---|
| [ISTP](https://www.istp.sk) | public | browse |  |
| [Profesia](https://www.profesia.sk) | private | browse |  |

Sources: <https://eures.europa.eu/living-and-working/living-and-working-conditions-europe/living-and-working-conditions-slovakia_en>

### Slovenia (SI)

| Site | Type | Access | Note |
|---|---|---|---|
| [Employment Service of Slovenia (ZRSZ)](https://www.ess.gov.si) | public | browse |  |
| [MojeDelo](https://www.mojedelo.com) | private | browse |  |

Sources: <https://eures.europa.eu/living-and-working/living-and-working-conditions-europe/living-and-working-conditions-slovenia_en>

## Baltics

### Estonia (EE)

| Site | Type | Access | Note |
|---|---|---|---|
| [Töötukassa job offers](https://www.tootukassa.ee/toopakkumised) | public | browse |  |
| [CV Keskus](https://www.cvkeskus.ee) | private | browse |  |
| [CV Online](https://www.cv.ee) | private | browse |  |

Sources: <https://eures.europa.eu/living-and-working/living-and-working-conditions-europe/living-and-working-conditions-estonia_en>

### Latvia (LV)

| Site | Type | Access | Note |
|---|---|---|---|
| [NVA (State Employment Agency)](https://www.nva.gov.lv) | public | browse |  |
| [CV Online](https://www.cv.lv) | private | browse |  |
| [CV Market](https://www.cvmarket.lv) | private | browse |  |

Sources: <https://eures.europa.eu/living-and-working/living-and-working-conditions-europe/living-and-working-conditions-latvia_en>

### Lithuania (LT)

| Site | Type | Access | Note |
|---|---|---|---|
| [Užimtumo tarnyba](https://uzt.lt) | public | browse |  |
| [CV Online](https://www.cvonline.lt) | private | browse |  |
| [CVbankas](https://www.cvbankas.lt) | private | browse |  |
| [CV.lt](https://www.cv.lt) | private | browse |  |

Sources: <https://eures.europa.eu/living-and-working/living-and-working-conditions-europe/living-and-working-conditions-lithuania_en>

## North America

### Canada (CA)

| Site | Type | Access | Note |
|---|---|---|---|
| [Job Bank (Government of Canada)](https://www.jobbank.gc.ca) | public | browse | Open data is only a monthly file, not live postings. |
| [Government of Canada jobs](https://www.canada.ca/en/services/jobs/opportunities/government.html) | government | browse |  |
| [Indeed Canada](https://ca.indeed.com) | private | browse |  |
| [Eluta](https://www.eluta.ca) | aggregator | browse | Lists jobs from employers' own sites. |
| [TalentEgg (students and graduates)](https://talentegg.ca) | private | browse |  |

Sources: <https://www.cs.ubc.ca/students/undergrad/careers/finding-career-opportunities/helpful-job-postings-sites>

### United States (US)

| Site | Type | Access | Note |
|---|---|---|---|
| [USAJOBS (federal jobs)](https://www.usajobs.gov) | government | API (key) | Free API key by e-mail at developer.usajobs.gov. Not yet built in. |
| [CareerOneStop (US Department of Labor)](https://www.careeronestop.org) | public | API (key) | Free API key on request. Not yet built in. |
| [Indeed](https://www.indeed.com) | private | browse |  |
| [LinkedIn Jobs](https://www.linkedin.com/jobs) | private | browse | Read only: never apply, connect or message. |
| [Dice (tech)](https://www.dice.com) | private | browse |  |
| [ZipRecruiter](https://www.ziprecruiter.com) | private | browse |  |
| [Glassdoor](https://www.glassdoor.com) | private | browse |  |

Sources: <https://developer.usajobs.gov>, <https://www.careeronestop.org/Developers>

## Oceania

### Australia (AU)

| Site | Type | Access | Note |
|---|---|---|---|
| [Workforce Australia](https://www.workforceaustralia.gov.au) | public | browse |  |
| [APSjobs (federal public service)](https://www.apsjobs.gov.au) | government | browse |  |
| [SEEK](https://www.seek.com.au) | private | browse | Australia's largest job site. |
| [Jora](https://au.jora.com) | aggregator | browse |  |
| [Indeed Australia](https://au.indeed.com) | private | browse |  |

Sources: <https://www.servicesaustralia.gov.au/looking-for-work-and-job-hunting>, <https://www.veteransemployment.gov.au/where-find-aps-jobs>, <https://apm.net.au/job-seekers/resources/best-job-sites-in-australia-to-find-employment>

## Left out

- **Monster / CareerBuilder**: CareerBuilder + Monster filed for bankruptcy in 2025 and sold its businesses. (<https://www.staffingindustry.com/news/global-daily-news/careerbuilder-monster-selling-businesses-filing-for-bankruptcy>)
- **Workopolis (Canada)**: Wound down by its owner (Indeed).
- **Blocket Jobb (Sweden)**: Could not be confirmed as active; Swedish postings are covered by Platsbanken.
