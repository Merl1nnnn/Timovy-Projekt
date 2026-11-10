# Словники для генератора мок-вакансій.
# Канонічні назви технологій — це ground truth. Аліаси використовуються лише
# для «брудного» відображення в тексті вакансії.

SPECIALIZATIONS: dict[str, dict[str, list[str]]] = {
    "Python": {
        "core": ["Python"],
        "pool": ["Django", "FastAPI", "Flask", "PostgreSQL", "Redis", "Docker",
                 "Celery", "AWS", "REST API", "Git", "Linux"],
    },
    "Java": {
        "core": ["Java"],
        "pool": ["Spring Boot", "Hibernate", "Kafka", "PostgreSQL", "Oracle", "Maven",
                 "Docker", "Kubernetes", "Microservices", "REST API", "Git"],
    },
    "DevOps": {
        "core": ["Linux"],
        "pool": ["Kubernetes", "Docker", "Terraform", "Ansible", "AWS", "Azure",
                 "Jenkins", "GitLab CI", "Prometheus", "Grafana", "Bash", "Python"],
    },
    "Data": {
        "core": ["SQL"],
        "pool": ["Python", "Apache Spark", "Airflow", "Power BI", "Snowflake", "Pandas",
                 "Databricks", "Kafka", "dbt", "Azure"],
    },
    "QA": {
        "core": [],
        "pool": ["Selenium", "Cypress", "Playwright", "Java", "Python", "JavaScript",
                 "Postman", "JMeter", "Jira", "REST API", "SQL"],
    },
    "Frontend": {
        "core": ["JavaScript"],
        "pool": ["TypeScript", "React", "Angular", "Vue.js", "HTML", "CSS", "Redux",
                 "Webpack", "Next.js", "Jest", "Git"],
    },
}

# Для QA одна з цих технологій завжди обов'язкова.
QA_CORE_CHOICES = ["Selenium", "Cypress", "Playwright"]

ALIASES: dict[str, list[str]] = {
    "JavaScript": ["js", "JS", "Javascript", "javascript"],
    "TypeScript": ["TS", "typescript"],
    "Kubernetes": ["k8s", "K8s", "kubernetes"],
    "PostgreSQL": ["postgres", "Postgres", "PostgresSQL", "psql"],
    "Python": ["python", "Python3"],
    "Spring Boot": ["spring boot", "SpringBoot"],
    "Vue.js": ["Vue", "VueJS", "vue"],
    "React": ["ReactJS", "React.js", "react"],
    "Next.js": ["NextJS", "next.js"],
    "Docker": ["docker"],
    "Apache Spark": ["Spark", "spark"],
    "Airflow": ["Apache Airflow"],
    "GitLab CI": ["Gitlab CI/CD", "GitLab pipelines", "gitlab-ci"],
    "Terraform": ["terraform", "TF"],
    "AWS": ["Amazon Web Services", "aws"],
    "Azure": ["MS Azure", "Microsoft Azure"],
    "Power BI": ["PowerBI", "PBI"],
    "SQL": ["sql"],
    "REST API": ["REST", "RESTful API", "REST APIs"],
    "Microservices": ["microservices", "mikroslužby", "microservice architecture"],
    "Pandas": ["pandas"],
    "Jest": ["jest"],
    "CSS": ["CSS3", "css"],
    "HTML": ["HTML5"],
    "Selenium": ["Selenium WebDriver"],
    "Linux": ["linux", "Unix/Linux"],
    "Bash": ["bash", "shell scripting"],
    "Kafka": ["Apache Kafka", "kafka"],
    "Git": ["git", "GIT"],
}

# Нетехнічні навички: входять у required_skills, але не в technologies.
SOFT_SKILLS: dict[str, dict[str, list[str]]] = {
    "English": {
        "sk": ["angličtina min. B2", "aktívna znalosť anglického jazyka", "English (B2+)"],
        "en": ["Fluent English", "English at B2 level or higher"],
    },
    "Slovak": {
        "sk": ["slovenčina alebo čeština na úrovni native"],
        "en": ["Slovak language is a must", "fluent Slovak or Czech"],
    },
    "Scrum": {
        "sk": ["skúsenosti s agilným vývojom (Scrum)", "práca v Scrum tíme"],
        "en": ["experience working in Scrum teams", "Agile/Scrum mindset"],
    },
    "Communication": {
        "sk": ["komunikatívnosť", "dobré komunikačné schopnosti"],
        "en": ["strong communication skills", "great communicator"],
    },
}

SENIORITY_TITLE_WORDS: dict[str, dict[str, list[str]]] = {
    "junior": {"sk": ["Junior", "Jr.", "Začínajúci"], "en": ["Junior", "Jr.", "Entry-level"]},
    # Порожній рядок: seniority не видно в заголовку, лише з досвіду в тексті.
    "medior": {"sk": ["Medior", "Mid-level", ""], "en": ["Mid-level", "Medior", ""]},
    "senior": {"sk": ["Senior", "Sr.", "Skúsený"], "en": ["Senior", "Sr.", "Senior"]},
    "lead": {"sk": ["Lead", "Tech Lead", "Team Lead"], "en": ["Lead", "Tech Lead", "Principal/Lead"]},
}

EXPERIENCE_LINES: dict[str, dict[str, list[str]]] = {
    "junior": {
        "sk": ["prvé skúsenosti s programovaním (aj školské projekty)", "0 – 1 rok praxe"],
        "en": ["0-1 years of experience, fresh graduates welcome", "first commercial experience is a plus, not a must"],
    },
    "medior": {
        "sk": ["2 – 4 roky praxe v podobnej pozícii", "aspoň 3 roky skúseností"],
        "en": ["2-4 years of professional experience", "at least 3 years in a similar role"],
    },
    "senior": {
        "sk": ["min. 5 rokov praxe", "5+ rokov skúseností s vývojom"],
        "en": ["5+ years of hands-on experience", "minimum 6 years in software development"],
    },
    "lead": {
        "sk": ["7+ rokov praxe, z toho aspoň 2 roky vedenie tímu", "skúsenosti s vedením tímu 4 – 8 ľudí"],
        "en": ["7+ years of experience incl. leading a team of engineers", "proven track record as a team lead"],
    },
}

TITLE_TEMPLATES: dict[str, dict[str, list[str]]] = {
    "Python": {
        "sk": ["{s} Python vývojár", "{s} Python programátor (m/ž)", "Python Developer {s}",
               "{s} Backend vývojár (Python)"],
        "en": ["{s} Python Developer", "{s} Backend Engineer (Python)",
               "Python Software Engineer - {s}", "{s} Python Dev"],
    },
    "Java": {
        "sk": ["{s} Java vývojár", "{s} Java programátor/ka", "Java Developer - {s}",
               "{s} Backend Developer (Java)"],
        "en": ["{s} Java Engineer", "{s} Java Developer", "Software Engineer (Java) - {s}"],
    },
    "DevOps": {
        "sk": ["{s} DevOps inžinier", "DevOps špecialista {s}", "{s} DevOps Engineer (m/ž)"],
        "en": ["{s} DevOps Engineer", "{s} Site Reliability Engineer", "DevOps Ninja - {s}",
               "{s} Cloud/DevOps Engineer"],
    },
    "Data": {
        "sk": ["{s} Dátový analytik", "{s} Data Engineer", "Dátový inžinier {s}"],
        "en": ["{s} Data Engineer", "{s} Data Analyst", "Data Wizard ({s})"],
    },
    "QA": {
        "sk": ["{s} QA tester", "Tester softvéru {s}", "{s} QA Automation Engineer"],
        "en": ["{s} QA Engineer", "{s} Test Automation Engineer", "QA Analyst - {s}"],
    },
    "Frontend": {
        "sk": ["{s} Frontend vývojár", "{s} Front-end programátor (m/ž)", "Webový vývojár – frontend {s}"],
        "en": ["{s} Frontend Developer", "{s} Front-End Engineer", "UI Developer - {s}",
               "{s} Frontend Rockstar"],
    },
}

TITLE_NOISE: list[str] = [" 🚀", " !!!", " | home office", " (TOP ponuka)", " – nový projekt", " #hiring"]

DUTIES: dict[str, dict[str, list[str]]] = {
    "Python": {
        "sk": ["vývoj a údržba backendových služieb", "návrh API a integrácie s externými systémami",
               "písanie testov a code review", "optimalizácia výkonu aplikácií"],
        "en": ["build and maintain backend services", "design APIs and third-party integrations",
               "write tests and do code reviews", "improve performance and reliability"],
    },
    "Java": {
        "sk": ["vývoj podnikových aplikácií pre bankový sektor", "analýza požiadaviek s product ownerom",
               "refaktoring legacy kódu", "code review a pair programming"],
        "en": ["develop enterprise applications for banking clients", "refine requirements with the product owner",
               "refactor legacy modules", "take part in code reviews"],
    },
    "DevOps": {
        "sk": ["správa cloudovej infraštruktúry", "budovanie CI/CD pipeline", "monitoring a riešenie incidentov",
               "automatizácia nasadzovania"],
        "en": ["own our cloud infrastructure", "build and improve CI/CD pipelines",
               "monitoring, alerting and on-call rotation", "automate everything you touch"],
    },
    "Data": {
        "sk": ["príprava dátových pipeline", "tvorba reportov pre manažment", "čistenie a modelovanie dát",
               "spolupráca s biznis analytikmi"],
        "en": ["build reliable data pipelines", "create dashboards for stakeholders",
               "clean and model data", "work closely with business analysts"],
    },
    "QA": {
        "sk": ["tvorba a údržba automatizovaných testov", "manuálne testovanie nových funkcionalít",
               "reportovanie chýb", "spolupráca s vývojármi na kvalite"],
        "en": ["create and maintain automated test suites", "exploratory and regression testing",
               "report and track bugs", "drive quality together with developers"],
    },
    "Frontend": {
        "sk": ["vývoj moderných webových aplikácií", "implementácia dizajnu z Figmy",
               "optimalizácia rýchlosti a prístupnosti", "spolupráca s UX tímom"],
        "en": ["develop modern web applications", "turn Figma designs into pixel-perfect UI",
               "care about performance and accessibility", "collaborate with UX designers"],
    },
}

LEAD_DUTY: dict[str, str] = {
    "sk": "vedenie tímu, plánovanie sprintov a mentoring",
    "en": "lead the team, plan sprints and mentor engineers",
}

COMPANIES: list[str] = [
    "TatraSoft s.r.o.", "Danubia Data a.s.", "Koala Byte s.r.o.", "Hronbit Solutions",
    "NovaSlav Tech", "Carpathia Cloud s.r.o.", "Bystrica Labs", "PixelPress Digital",
    "Vrchol Systems a.s.", "Orava Analytics", "Mostík Software s.r.o.", "Sigma Kódex s.r.o.",
    "BlueOx Fintech", "Zelený Kód a.s.", "Lipa Logistics IT",
]

COMPANY_KINDS: dict[str, list[str]] = {
    "sk": ["softvérová spoločnosť", "fintech startup", "IT konzultačná firma", "produktová firma"],
    "en": ["software company", "fintech startup", "IT consultancy", "product company"],
}

PRODUCTS: dict[str, list[str]] = {
    "sk": ["bankové aplikácie", "logistický softvér", "e-commerce platformu", "nástroje na analýzu dát"],
    "en": ["banking apps", "logistics software", "an e-commerce platform", "data analytics tools"],
}

INTRO_TEMPLATES: dict[str, list[str]] = {
    "sk": ["{c} je rastúca {k} s tímami na Slovensku a v Česku.",
           "V {c} vyvíjame {p} pre klientov z celej Európy.",
           "Sme {k} {c} a hľadáme nových kolegov do nášho tech stacku!"],
    "en": ["{c} is a fast-growing {k} with offices in Slovakia.",
           "At {c}, we build {p} used by customers across Europe.",
           "Join {c} – a {k} that ships every week."],
}

BENEFITS: dict[str, list[str]] = {
    "sk": ["stravné lístky", "MultiSport karta", "flexibilný pracovný čas", "13. a 14. plat",
           "5 dní dovolenky navyše", "notebook podľa vlastného výberu", "firemné teambuildingy",
           "príspevok na DDS", "platené certifikácie"],
    "en": ["meal vouchers", "MultiSport card", "flexible working hours", "5 extra vacation days",
           "budget for conferences & certifications", "brand new MacBook", "team buildings",
           "pension contribution"],
}

# Канонічне місто -> варіанти відображення.
CITY_DISPLAY: dict[str, list[str]] = {
    "Bratislava": ["Bratislava", "Bratislava - Staré Mesto", "Bratislava, Slovensko",
                   "Bratislava, Bratislavský kraj, Slovakia", "BA"],
    "Košice": ["Košice", "Kosice", "Košice - Juh", "Košice, Slovakia"],
    "Žilina": ["Žilina", "Zilina", "Žilina, Žilinský kraj"],
}

REMOTE_DISPLAY: dict[str, list[str]] = {
    "sk": ["Práca z domu", "Remote", "Home office (celé Slovensko)"],
    "en": ["Remote", "Slovakia (Remote)", "Anywhere in EU (remote)"],
}

EMPLOYMENT_DISPLAY: dict[str, dict[str, list[str]]] = {
    "full_time": {"sk": ["plný úväzok", "TPP – plný úväzok"], "en": ["Full-time"]},
    "part_time": {"sk": ["skrátený úväzok", "čiastočný úväzok"], "en": ["Part-time"]},
    "contract": {"sk": ["živnosť", "kontrakt / živnosť"], "en": ["Contract", "Contractor (B2B)"]},
}

# Як LinkedIn показує seniority в criteria (навмисно з втратою інформації).
LINKEDIN_LEVEL: dict[str, str] = {
    "junior": "Entry level",
    "medior": "Associate",
    "senior": "Mid-Senior level",
    "lead": "Mid-Senior level",
}
