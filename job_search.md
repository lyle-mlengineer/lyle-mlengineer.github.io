## Skipper

- Skipper is an ai agent that helps me in my job search.

- The agents main role is to take in a potential job from:
    - A company website or careers page
    - A link to a job board
    - A description of the job

- The agent then analyzes the job and:
    - Summarizes it
    - Does research on the compnay either web search or RAG
    - Writes me a cv, both pdf and doc based on the job description and my portfolio
    - Writes a cover letter
    - Writes a good tell me about yourself
    - Writes a good work history
    - Writes a good projects you are proud of
    - Writes the email to send
    - A likely technical interview with answers
    - A likely behavioral interview with answers

- The agent has a dashboard that keeps track od jobs and their application status; this can be updated by me
- The agent has a jobs page for all the jobs as well as a custom page for each job
- A companies page for all companies and a custom page for each company

- The landing page is my portfolio, but a new dashboard link is added that requests a password and username to access the dashboard

- Make the application stylish and responsive and follow the portfolio styling
- The tech stack is html, css, vanilla javascript and jinja tags with fastapi and sqlite3. Use fastapi background jobs for heavy processing with loading indicators for the frontend that poll for updates
- Create the skills for the agent which include:
    1. Job details extraction (extract meaningful details), from company website, careers page or job text
    2. Job summarization
    3. Company research
    4. cv writing
    5. cover letter writing
    6. email writing
    7. tell me about yourself, given job, company and portfolio
    8. work history, given job, company and portfolio
    9. proud project, given job, company and portfolio
    10. technical interview with answers
    11. Behavioral interview with answers
- Create the agent also that can use those skills
- Create the application in the job_search folder
- Create a generic llm provider that can be implemented for the various providers; then implement a concrete provider for Groq with openai gpt oss;
- For web search create a generic provider with implementations for serper and duckduckgo