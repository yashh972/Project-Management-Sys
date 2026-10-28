# Agile CodeBoard: User Guide

A first-time walkthrough of every page: what it is for, how it works from the first click to the last, and what the numbers mean.

Agile CodeBoard is a project-management web app. People create **tasks**, group them into **projects** and two-week **sprints**, track them to completion, and the system adds analytics, late-risk warnings and assignee suggestions on top of that history.

- Local address: <http://localhost:9090/>
- Diagrams of the whole system: [flow-diagram.html](flow-diagram.html)

---

## Contents

1. [Before you start: the ideas you need](#1-before-you-start-the-ideas-you-need)
2. [Logging in and your account](#2-logging-in-and-your-account)
3. [The sidebar at a glance](#3-the-sidebar-at-a-glance)
4. [Dashboard](#4-dashboard)
5. [Creating work: the New menu and the issue form](#5-creating-work-the-new-menu-and-the-issue-form)
6. [Browse: finding and bulk-editing issues](#6-browse-finding-and-bulk-editing-issues)
7. [Inside one issue](#7-inside-one-issue)
8. [Sprints (the backlog)](#8-sprints-the-backlog)
9. [Taskboard](#9-taskboard)
10. [Tags](#10-tags)
11. [Analytics, tab by tab](#11-analytics-tab-by-tab)
12. [Exports: CSV and PDF](#12-exports-csv-and-pdf)
13. [Alerts and email](#13-alerts-and-email)
14. [Admin area](#14-admin-area)
15. [A typical week, start to finish](#15-a-typical-week-start-to-finish)
16. [Glossary and FAQ](#16-glossary-and-faq)

---

## 1. Before you start: the ideas you need

| Word | Meaning |
|---|---|
| **Issue** | Anything you can track. There are three kinds: **Task**, **Bug** and **Project**. |
| **Project** | A container for tasks and bugs (for example "Website Redesign"). It can also hold sub-projects. |
| **Task / Bug** | A piece of work with one **owner** (assignee). A bug is a task that fixes a defect. |
| **Status** | Where the issue is: **New** → **Active** → **Completed**, or **On Hold** if paused. Completed counts as closed. |
| **Owner / Author** | The owner does the work. The author created the issue. They can be the same person. |
| **Priority** | Low, Normal or High. |
| **Sprint** | A two-week planning block (Sprint 13 is the current one). Projects and tasks are scheduled into sprints. |
| **Hours** | *Estimate* (hours total), *remaining* and *spent*. These drive workload numbers. |
| **Due date** | The date the work must be done. "On time" means closed on or before it. |
| **Tags** | Words starting with `#` in a description (for example `#backend`). They group related issues and improve assignee suggestions. |
| **Watchers** | People who get notified about changes to an issue. |
| **Dependency** | "This can't start/finish until that one does." |

Every change to an issue (status, owner, hours, sprint) is saved with the time and the person who made it. That history powers the activity feed, the burndown chart and the analytics.

### Roles

| Role | What you can do |
|---|---|
| **Admin** | Everything, including the Admin area and the full Analytics dashboard. |
| **Manager** | Everything a user can do, plus extras such as dragging projects between sprints and deleting issues. |
| **User** | Create and work on issues, comment, use the taskboard. Analytics shows only your own tasks. |
| **Client** | Basic access to what they are given. |

---

## 2. Logging in and your account

### First login
1. Open <http://localhost:9090/login>.
2. Type your **username or email** and your **password**, then press **Log in**.
3. You land on your **Dashboard**.

If the password is wrong you see "Invalid login information, try again." Ask an admin for a reset (admins reset passwords at **Admin → Users**).

### Your account page
Click your name at the bottom of the sidebar, then **My account** (address `/user`).

- **Name and email:** shown in the app and in emails.
- **Password:** type the current password, then the new one twice. Do this on your first day.
- **API key:** lets scripts call the REST API as you. Keep it private.
- **Theme and language:** change how the app looks.
- **Task colour:** the colour of your cards on boards and calendars.
- **Avatar:** upload a profile picture.
- **Preferences:** turn off the "due issue" emails, turn off notifications for your own actions, or turn off the text editor.

Press **Save** after changing anything.

### Logging out
Use the menu at the bottom of the sidebar and choose **Log out**.

---

## 3. The sidebar at a glance

| Item | Takes you to | Purpose |
|---|---|---|
| **Search box** (press `/`) | Search results | Find any issue by name or text. |
| **New** | The create menu | Start a task, bug, project, sub-project (and sprints, for admins). |
| **Dashboard** | Your home page | What is assigned to you. |
| **Analytics** / **My Analytics** | `/analytics` | Charts, projects, alerts (admins also get team and performance). |
| **Browse** | Issue lists | Open, closed, created by me, assigned to me, by type, tags. |
| **Sprints** | `/backlog` | Plan projects into sprints. |
| **Taskboard** | Kanban board | Move work across status columns. |
| **Admin** (admins only) | `/admin` | Users, groups, sprints, settings. |
| Your name | Account menu | My issues, My account, Log out. |

---

## 4. Dashboard

**Where:** the home page, or **Dashboard** in the sidebar.
**For:** the first thing you check each morning.

**How it works from start to end**
1. The page loads the issues where you are the owner (and the widgets you chose).
2. Each box on the page is a **widget**: for example your tasks, bugs, projects, a watch list, recent comments or a project tree.
3. Use the dashboard settings to add, remove or reorder widgets. The layout is saved per person.
4. Click any issue to open it.

**Tip:** a short list on the dashboard means you have little assigned. The Analytics "My Open Tasks" tile shows the same count with overdue ones highlighted.

---

## 5. Creating work: the New menu and the issue form

### Step by step
1. Click **New** in the sidebar and choose **Task**, **Bug** or **Project**.
   - While viewing a project, the same menu also offers **Task** and **Sub-project** inside it.
   - While viewing a task, it offers **Child task** and **Related task**.
2. Fill in the form:

| Field | What to enter |
|---|---|
| **Title** | A short name that says what "done" looks like. |
| **Type** | Task, Bug or Project (already set from the menu). |
| **Parent** | The project it belongs to. |
| **Priority** | Low, Normal, High. |
| **Assignee** | Who will do it. Use **Suggest assignee** (below). |
| **Status** | Starts as New. |
| **Start date / Due date** | When work begins and the deadline. Needed for on-time tracking. |
| **Estimate (hours)** | How long you expect it to take. Needed for workload numbers. |
| **Size estimate** | Optional points (1, 2, 3, 5, 8). |
| **Sprint** | Which sprint it belongs to. |
| **Repeat** | Optional repeating schedule. |
| **Description** | Details and acceptance criteria. Add `#tags` here. |

3. Press **Save**. You are taken to the new issue.

### Suggest assignee (smart assignment)
Under the **Assignee** field is a **Suggest assignee** button.

1. Fill in the type, priority, due date, estimate and any `#tags` first. The suggestion uses these.
2. Press **Suggest assignee** and wait about 3 seconds ("Scoring the team…").
3. You see up to five people, best first. Each card shows:
   - a **fit score** out of 100 (green 70+, amber 50–69, red below 50),
   - the predicted **late risk** and **expected days**,
   - **reasons**: open tasks and hours already queued, record on similar work, recent on-time rate.
4. Press **Assign** on a card to fill the Assignee field, then save as usual.

How to read it: a person with a lighter workload and a good on-time record scores higher. A person with fewer than 3 finished tasks is marked **limited history** and loses 15 points, because the system has little evidence about them. It is a recommendation only; you decide.

---

## 6. Browse: finding and bulk-editing issues

**Where:** **Browse** in the sidebar.

### The menu
- **Open** and **Closed:** all issues by state.
- **Created by me** and **Assigned to me:** your own.
- **By type:** only tasks, bugs or projects.
- **Tags:** a cloud of all tags (see [Tags](#10-tags)).

### Working with the list
1. Pick a list from the menu. The table shows the issues.
2. Use the filter bar above the table to narrow by status, type, owner, author, parent project and so on.
3. Click a column heading to sort. The default order is priority.
4. Results are paged (50 per page).
5. **Export** downloads the current list as a CSV file.

### Bulk edit
1. Open **Show Bulk Actions**.
2. Tick the issues you want.
3. Choose **Update All Selected Tasks**, set the fields the dialog offers (for example the status), and confirm.

Use this to change a whole batch at once instead of opening each issue.

### Search
Press `/` anywhere, type, and press Enter. Results show matching issues, open ones first.

---

## 7. Inside one issue

Click any issue name to open its page.

**The top:** title, status, owner, priority, dates, hours, sprint, tags and description. Buttons let you edit, copy, close or reopen it.

**The tabs below it**

| Tab | What it shows |
|---|---|
| **Comments** | The conversation. Add a comment at the bottom; the count appears on the tab. You can close the issue in the same step. |
| **History** | Every change with who and when (status moves, owner changes, hours updates). |
| **Watchers** | People following the issue. Add or remove them. |
| **Sibling tasks** | Other tasks under the same parent. |
| **Child tasks** | Tasks under this one (for projects). |
| **Dependencies** | What this blocks and what blocks it. Add a dependency by issue number and choose the type (FS, FF, SS, SF: finish or start relationships). |
| **Files** | Upload attachments; switch between tile and table view. |

**Typical flow for a task**
1. The owner opens the issue and sets status **Active** (work starts).
2. They add progress comments and update **hours remaining**.
3. When finished they set **Completed**. The closed date is stamped and remaining hours go to 0.
4. If it must be redone, **Reopen** it. A reopen counts against quality in the performance score.

---

## 8. Sprints (the backlog)

**Where:** **Sprints** in the sidebar (address `/backlog`).
**For:** deciding which projects happen in which two-week sprint.

**How it works**
1. The **left panel** is the **Backlog**: open projects that are not yet in any sprint.
2. The **right side** lists **sprints** from newest to oldest, each with its dates (for example *Sprint 12, 9/15/26 – 9/28/26*). Click the triangle to expand a sprint and see its projects.
3. **Drag a project** from the backlog into a sprint to schedule it. Drag it back to the backlog to unschedule. (Managers and admins can drag.) Dragging does three things: it sets the project's sprint, it moves all of the project's tasks into that sprint (so they appear on that sprint's Taskboard), and, when you reorder inside one list, it saves the priority order, with the most important project at the top.
   - **New projects:** a project you create with **Add Project** (or **New → Project**) has no sprint yet, so it appears in the **Backlog** panel on the left. It is not in a sprint until you drag it across.
   - **Filter:** the panel only lists projects owned by people in your groups. Use **Groups → All projects** to see the rest.
4. Each sprint has a **Taskboard** button that opens its board.
5. The filter at the top of the backlog panel switches between **My groups**, **All projects**, **My projects** and each group. If the backlog looks empty, check this filter first.
6. **Show Future Sprints** reveals upcoming sprints.

Admins create new sprints from **New → Sprint** (or Admin → Sprints).

---

## 9. Taskboard

**Where:** **Taskboard** in the sidebar, or the **Taskboard** button on a sprint. The arrows at the bottom right move to the previous or next sprint; the calendar button jumps to the current one.
**For:** daily work and stand-ups.

**How to read the board**
- **Columns are statuses:** **New** (not started), **Active** (being worked on), **Completed** (done) and **On Hold** (paused). The number on each column heading is how many tasks it holds.
- **Rows are projects:** each row starts with a project card on the left (project name, owner, due date). The tasks of that project sit to its right, in the column that matches their status.
- **Each task card shows:** its number and due date, the title, the owner, a **High** or **Low** priority tag (Normal shows nothing) and the hours left. The coloured edge is the owner's colour. Hover over a card for the author and description.
- **Completed cards** are dimmed with a line through the title.

**How to use it**
1. Pick what to show with the **Groups** button: **All tasks**, **My groups**, **My tasks**, or one group. The small line under the buttons says what you are looking at. If cards seem to be missing, this filter is the first thing to check.
2. **Start a task:** drag its card from **New** to **Active**.
3. **Pause a task:** drag it to **On Hold**. Drag it back to **Active** to continue.
4. **Finish a task:** drag it to **Completed**. Its closed date is stamped and its hours left become 0. Drag it out again to reopen it.
5. Each move is saved straight away and appears in the issue's history. The column numbers update as you drag.
6. **Edit a card:** click it to change its title, hours, due date and owner, or to add a comment and log hours spent.
7. **Add a task to a project:** press the **+** on the project card.
8. **Burndown:** when a single group is selected, the **Burndown** button shows remaining work against time for the sprint. A line that falls steadily means the sprint is on pace; a flat line means work is stuck.

## 10. Tags

Type `#name` anywhere in an issue description (for example `#backend #api`). Open **Browse → Tags** to see a tag cloud, and click a tag to list every issue with it.

Good habits: use a small, consistent set (`frontend`, `backend`, `design`, `testing`, `docs`, `devops`). Tags also tell the assignment model what kind of work a task is, so people with a good record on that kind of work rank higher.

---

## 11. Analytics, tab by tab

**Where:** **Analytics** (admins) or **My Analytics** (everyone else) in the sidebar.

### How the page is organised
- **Header:** a greeting, a **period switch** (This Week / This Month / Quarter), **CSV** and **PDF** export, and **Recompute insights** (admins).
- **Tabs:** Overview, Projects, Alerts, Team, Performance, Compare.
- **Who sees what:** admins see all six tabs for everyone. Everyone else sees Overview, Projects and Alerts, limited to the tasks assigned to them and the projects those belong to.
- **Freshness:** counts, calendar and lists update immediately. Scores and late-risk numbers update only when someone presses **Recompute insights** (or the scheduled job runs).

### Overview

**What it is:** the one-screen summary.

**The five tiles** (click any to go deeper):

| Tile | Meaning | Click goes to |
|---|---|---|
| **Total Tasks** (*My Tasks*) | Number of tasks. The small arrow compares tasks created this period with the previous one. | The task list |
| **Active Projects** | Projects not yet closed, and how many are at risk. | The Projects tab |
| **Completed** | Tasks closed in the chosen period, compared with the previous period. | Closed issues |
| **On-time Rate** | Of tasks completed in the period that had a due date, the share closed on or before it. | Performance tab (admins) |
| **Team Members** (*My Open Tasks*) | People on the team and how many have open work. For non-admins: your open tasks and how many are overdue. | Team tab (admins) / your open list |

**Project Performance chart:** two lines, tasks **created** and tasks **completed**, per day (week view), per 3 days (month) or per week (quarter). When the completed line stays above created, the backlog is shrinking.

**Recent Activity:** the latest status changes, reassignments, estimate updates and comments, newest first, with who and how long ago. It includes comments you add right away. Non-admins see activity on their own tasks and their own actions.

**Tasks-due calendar:** an interactive calendar.
1. It opens on the current week with today highlighted.
2. Use **‹** and **›** to move a week (or a month in Month view), and **Today** to jump back.
3. Switch **Week / Month** to change the layout.
4. Each day shows a **badge** with how many tasks are due: **red** if overdue open tasks are among them, **violet** if tasks are still open, **green** if everything due that day is done.
5. **Click a day** to list its tasks: name, project, open / overdue / completed, late risk (if 40% or more) and the owner's avatar. Click a task to open it.
6. On a day with nothing due you get a **Next due** link.

**Likely to slip** (shown with the side lists): open tasks the model rates as most likely to finish late, with the percentage.

### Projects

**What it is:** every project and where it stands.

1. Four counters at the top: **On track**, **In progress**, **At risk**, **Completed**.
2. The table lists each project with a **progress bar** (completed tasks ÷ all its tasks), due date, the people doing most of the work, and a **status pill**.
3. How the status is decided:
   - **Completed:** the project is closed.
   - **At risk:** progress is more than 15 points behind the time elapsed, or the average late risk of its open tasks is above 60%, or three or more tasks are overdue.
   - **On track:** progress is at or ahead of time elapsed.
   - **In progress:** anything in between.
4. **Click a project name** to open its own analytics page (next section).

#### The project analytics page
- **Header:** project name, status pill, **CSV** and **PDF** buttons for just this project, and a link back to the project itself.
- **Five tiles** (all clickable): **Progress**, **Open tasks** (with hours remaining), **Overdue**, **On-time rate**, **Avg late risk**.
- **Weekly flow:** bars of tasks created and completed for each of the last 8 weeks.
- **Tasks table:** open tasks first, soonest due first, with owner, status, due date and late risk.
- **By status** bars and a **Team** list (admins only) with each person's open, done and late tasks and hours left.

### Alerts

**What it is:** a to-do list of things going wrong, so nobody has to hunt for them.

1. Three counters: **Overdue** (past due date, still open), **Due in 2 days**, and **Late-risk** (the model rates the task 40% or more likely to finish late).
2. Below, tasks are grouped by owner. Each line has a coloured tag (Overdue, Due soon, Late risk) and links to the task.
3. Admins can press **Email owners now** to send each owner a digest of their own alerts. The same digest is sent daily by a scheduled job. Email must be set up first (see [Alerts and email](#13-alerts-and-email)).
4. Non-admins see only their own alerts and have no email button.

### Team (admins only)

**What it is:** workload balance.

1. One card per person with their avatar, number of open tasks and **open hours**.
2. The bar shows open hours against a **40-hour capacity**: green below 60%, amber 60–89%, red 90% or more. Overdue tasks are counted on the card.
3. Use it to spot people who are overloaded or idle, then rebalance by reassigning tasks.

### Performance (admins only)

**What it is:** a fair ranking of people, based on history.

**Employee Performance** lists each person with:
- a **score from 0 to 100** and a **rank**,
- a **behaviour group** (for example steady, fast but risky) found by clustering,
- on-time % compared with the on-time % expected for the work they were given,
- speed, how often work was reopened, estimate accuracy, weekly throughput and a trend.

**How the score is built:** reliability 35%, speed 25%, quality 15%, estimation 10%, volume 15%. The system first learns what is normal for a task *without knowing who did it*, then judges each person against that. So someone given harder work is not ranked below someone given easy work. People with fewer than 8 closed tasks get no score, and small samples are pulled toward the team average.

**Likely to slip:** the open tasks with the highest late risk.

**How the ML works:** a short explanation and the model's quality figures, so you can judge how much to trust it.

Treat the score as a prompt for a conversation, not a verdict.

### Compare (admins only)

**What it is:** a head-to-head of two people.

1. Pick **Person A** and **Person B** from the two lists.
2. A **radar chart** overlays their five measures. A **table** compares every number and marks the better one.
3. Below, written **strengths** and **concerns** for each person.

---

## 12. Exports: CSV and PDF

**Where:** the **CSV** and **PDF** buttons at the top of the Analytics overview and of each project page.

| | CSV | PDF |
|---|---|---|
| **Opens in** | Excel, Google Sheets | Any PDF reader |
| **Best for** | Further analysis | Sharing and printing |

**What is included**
- *Overview export:* projects, team workload, employee performance (admins) and task alerts.
- *Project export:* a summary, tasks by status, the team (admins) and the full task list with owner, due date, hours left and late risk.
- Non-admins get the same layout containing only their own data.

Text that starts with `=`, `+`, `-` or `@` is prefixed so a spreadsheet will not run it as a formula.

---

## 13. Alerts and email

**Task alerts:** overdue tasks, tasks due within 2 days, and tasks the model rates 40%+ likely to slip.

**Where you see them**
- In the app, on the **Alerts** tab.
- By email, if email is set up. Each owner receives one digest listing their own alerts with links.

**Email setup:** the digest is only sent when the setting `mail.from` (a sender address) is configured. Until then, pressing **Email owners now** tells you email is not configured. People can switch off due-issue emails on their account page.

**Scheduling (admin):** run these once a day, in this order:
1. `ml/run_analytics.py`: refresh scores and late-risk.
2. `ml/assign_model.py train`: refresh the assignment model.
3. `php cron/task_alerts.php`: send the digests.

---

## 14. Admin area

**Where:** **Admin** in the sidebar (admins only).

| Section | What you do |
|---|---|
| **Users** | Add a user, edit name, email, role and rank, set a new password, deactivate or restore someone. |
| **Groups** | Create teams (for example Engineering), add members and choose a manager. Groups drive the backlog filters. |
| **Sprints** | Create sprints and edit their dates. |
| **Settings** | Site name, description, theme, public registration, mail sender and more. |
| **Plugins** | Turn extensions on or off. |

**Adding a person, start to finish**
1. **Admin → Users → New user.**
2. Enter username, name, email, a role (and rank), and a password.
3. Save and give the person the username and password. They should change it on their account page.
4. Add them to a group if they belong to a team.

If you forget the admin password, run `php reset-password.php admin` in the project folder and follow the prompt.

---

## 15. A typical week, start to finish

**Monday: plan**
1. A manager opens **Sprints** and drags this fortnight's projects into the current sprint.
2. For each project they create tasks with **New → Task**, fill in estimate, due date and tags, and use **Suggest assignee** to pick owners.
3. They open **Analytics → Team** to check that nobody is over 40 hours.

**Every day: work**
1. Each person opens **Dashboard**, or **Taskboard** for the sprint.
2. They drag a card to **Active** when they start, comment on progress, and drag to **Completed** when done.
3. Overdue or risky tasks appear on the **Alerts** tab and in the owner's email.

**Friday: review**
1. Open **Analytics → Overview** and set the period to **This Week**. Check the created-versus-completed lines and the on-time rate.
2. Open **Projects** to see which projects are at risk, then open one for its weekly flow and task table.
3. Press **Recompute insights** so the scores and late-risk reflect the week.
4. Export a **PDF** for the status meeting.

**End of sprint**
1. Check the **Taskboard** burndown.
2. Move unfinished work to the next sprint (edit each issue's Sprint field, or use **Bulk Actions** if the dialog offers it).
3. Open **Performance** and **Compare** for one-to-one conversations.

---

## 16. Glossary and FAQ

**What does "late risk" mean?** The model's estimate, as a percentage, of how likely an open task is to finish after its due date. 40% or more raises an alert.

**What is "On-time rate"?** Of the tasks finished in a period that had a due date, the percentage finished on or before it.

**Why is my Analytics page shorter than an admin's?** Non-admins see only the tasks assigned to them, and the Team, Performance and Compare tabs are hidden because they show other people's data.

**Why is the Sprints backlog empty?** Check the filter at the top of the backlog panel; it defaults to **My groups**. Switch to **All projects**.

**Why did a new comment not show in Recent Activity?** It should appear immediately. If not, reload the page.

**Why are scores missing for someone?** They have fewer than 8 closed tasks. The assignment suggestion shows them as **limited history** below 3.

**Why does Suggest assignee take a few seconds?** It runs the model on demand.

**Are the scores a performance review?** No. They are signals based on task history and are only as good as the data. Use them to ask questions.

**Where is my data stored?** In a single SQLite file, `phproject.db`, in the project folder. Back it up regularly.
