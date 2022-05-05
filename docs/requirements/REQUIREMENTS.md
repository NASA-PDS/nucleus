# Nucleus High Level Requirements

## Data Pipeline Requirements

### Data Pipeline Authoring

| Requirement                                                                                                                                                                                                                        | Importance  | Priority | Rationale / Comments |
|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------|----------|----------------------|
| Nucleus shall define data pipelines by combining pluggable processing nodes (preferably docker containers).                                                                                                                        | Must have   |          |                      |
| The technologies used for Nucleus data pipelines shall not restrict the supported types of data that can be processed. The supported types of data should be only dependent on the capabilities of the pluggable processing nodes. | Must have   |          |                      |
| Nucleus shall create data pipelines as directional graphs, where nodes can have multiple sources.                                                                                                                                  | Must have   |          |                      |
| Nucleus shall create data pipelines as directional graphs, where nodes can have multiple sinks.                                                                                                                                    | Must have   |          |                      |
| Nucleus shall execute process models (E.g.: [Business Process Model and Notation](https://en.wikipedia.org/wiki/Business_Process_Model_and_Notation)) created by external graphical modeling tools                                 | Should have | Very low |                      |
| Nucleus shall provide a graphical modeling software to author data pipelines by combining pluggable components available in a library. This can be a separate module.                                                              | Should have | Very low |                      |
| Nucleus shall provide an interface to import/export data pipelines configurations (This can be version controlled in a source code repository too).                                                                                | Must have   |          |                      |
| Nucleus shall provide ways to add branching logic to take different paths in the data pipeline on errors.                                                                                                                          | Must have   |          |                      |
| Nucleus should enable Retry policy for each data pipeline.                                                                                                                                                                         | Must have   |          |                      |

### Data Pipeline Management

| Requirement                                                          | Importance | Priority | Rationale / Comments |
|----------------------------------------------------------------------|------------|----------|----------------------|
| Nucleus shall add/create a data pipeline.                            | Must have  |          |                      |
| Nucleus shall update a data pipeline.                                | Must have  |          |                      |
| Nucleus shall deactivate a data pipeline.                            | Must have  |          |                      |
| Nucleus shall activate a data pipeline.                              | Must have  |          |                      |
| Nucleus shall delete a data pipeline.                                | Must have  |          |                      |
| Nucleus shall assign a priority to a data pipeline before execution. | Must have  |          |                      |

### Data Pipeline Execution

| Requirement                                                                                  | Importance | Priority | Rationale / Comments |
|----------------------------------------------------------------------------------------------|------------|----------|----------------------|
| Nucleus shall execute predefined data pipelines.                                             | Must have  |          |                      |
| Nucleus shall execute parallel branches in data pipelines concurrently.                      | Must have  |          |                      |
| Nucleus shall execute multiple pipelines concurrently.                                       | Must have  |          |                      |
| Nucleus should retry data pipeline execution based on a predefined retry policy on failures. | Must have  |          |                      |

### ETL Operations

| Requirement                                                                                                                                                                                    | Importance  | Priority | Rationale / Comments |
|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------|----------|----------------------|
| Nucleus shall support ETL operations.                                                                                                                                                          | Must have   |          |                      |
| Nucleus shall execute ETL jobs in batch mode where data is extracted, transformed and loaded as batches.                                                                                       | Must have   |          |                      |
| Nucleus shall execute ETL processes in real-time mode where data is extracted, transformed and loaded in real-time as soon as data is received (this can also be considered as streaming ETL). | Should have |          |                      |

### Data Pipeline Lifecycle Management

| Requirement                                                              | Importance  | Priority | Rationale / Comments |
|--------------------------------------------------------------------------|-------------|----------|----------------------|
| Nucleus shall initiate a data pipeline.                                  | Must have   |          |                      |
| Nucleus shall suspend a data pipeline.                                   | Must have   |          |                      |
| Nucleus shall resume a data pipeline.                                    | Must have   |          |                      |
| Nucleus shall terminate a data pipeline.                                 | Must have   |          |                      |
| Nucleus shall assign a priority to a data pipeline during the execution. | Should have |          |                      |

### Data Pipeline Triggers

| Requirement                                                                                                                       | Importance  | Priority | Rationale / Comments                          |
|-----------------------------------------------------------------------------------------------------------------------------------|-------------|----------|-----------------------------------------------|
| Nucleus shall trigger the execution of a data pipeline on demand by a human user or external system.                              | Must have   |          |                                               |
| Nucleus shall trigger the execution of a data pipeline based on a schedule.                                                       | Should have |          | How can we provide cost optimized scheduling? |
| Nucleus shall trigger the execution of a data pipeline automatically based on a data file receive event.                          | Must have   |          |                                               |
| Nucleus shall trigger the execution of a data pipeline automatically based on a change in a database table (Change Data Capture). | Should have |          |                                               |
| Nucleus shall trigger the execution of a data pipeline automatically based on a message/event (E.g.: Kafka event, RabbitMQ event) | Should have |          |                                               |

## Application Programming Interface Requirements

### Representative State Transfer (REST) based Application Programming Interface (API)

| Requirement                                                                                                                                                                                                                       | Importance | Priority | Rationale / Comment |
|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------|----------|---------------------|
| Nucleus shall provide a Representative State Transfer (REST) based Application Programming Interface (API) for data pipeline life cycle management (initiate, suspend, resume, terminate).                                        | Must have  |          |                     |
| Nucleus shall provide a Representative State Transfer (REST) based Application Programming Interface (API) for data pipeline monitoring (with ability to check progress and statistics on both current and historical pipelines). | Must have  |          |                     |
| Nucleus shall provide a Representative State Transfer (REST) based Application Programming Interface (API) to import and delete predefined data pipelines.                                                                        | Must have  |          |                     |

### Command Line Interface (CLI)

| Requirement                                                                                                                                                                                                                       | Importance | Priority | Rationale / Comment |
|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------|----------|---------------------|
| Nucleus shall provide a Command Line Interface (CLI) for process management (initiate, suspend, resume, terminate).                                                         | Must have  |          |                     |
| Nucleus shall provide a Command Line Interface (CLI) for data pipeline monitoring (with ability to check progress and statistics on both current and historical pipelines). | Must have  |          |                     |
| Nucleus shall provide a Command Line Interface (CLI) based Application Programming Interface (API) to import and delete predefined data pipelines.                          | Must have  |          |                     |

### Programming Language Support

| Requirement                                                                                                                                                            | Importance  | Priority | Rationale / Comment                                 |
|------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------|----------|-----------------------------------------------------|
| Nucleus shall provide a python language wrapper for process management (initiate, suspend, resume, terminate).                                                         | Must have   |          |                                                     |
| Nucleus shall provide a python language wrapper for data pipeline monitoring (with ability to check progress and statistics on both current and historical pipelines). | Must have   |          |                                                     |
| Nucleus shall provide a python language support to define branching logic and iteration in data pipeline definitions, when applicable.                                 | Should have |          | Adding if conditions and for loops into definitions |
| Python language wrapper for pipeline definition?                                                                                                                       | Should have |          |                                                     |

## Logging and Auditing Requirements

| Requirement                                                                                                                                                                        | Importance | Priority | Rationale / Comment |
|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------|----------|---------------------|
| Nucleus shall log the Initialization, Termination, Processing progress, Warnings and Errors of each component.                                                                     | Must have  |          |                     |
| Nucleus shall provide a way to check the logs of all components in a single place, without having to check the logs for each and every component separately.                       | Must have  |          |                     |
| Nucleus shall log each user access attempts to the system with the details of date and time of the event, outcome of the access attempt (allowed/denied), user name and user roles | Must have  |          |                     |

## Versioning, Backups and Restore Requirements

| Requirement                                                                                                                                                                               | Importance | Priority | Rationale / Comment |
|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------|----------|---------------------|
| Nucleus shall create versions of data pipeline definitions and other deployment configurations.                                                                                           | Must have  |          |                     |
| Nucleus shall backup the versions of data pipeline definitions, other deployment configurations and administration related data such as user accounts, user roles, permissions and logs.  | Must have  |          |                     |
| Nucleus shall restore the versions of data pipeline definitions, other deployment configurations and administration related data such as user accounts, user roles, permissions and logs. | Must have  |          |                     |

## Notification Requirements

| Requirement                                                                                                                                                                                                                                                                                                                                                                       | Importance | Priority | Rationale / Comment |
|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------|----------|---------------------|
| Nucleus shall send email notifications based on predefined events and based on user roles.                                                                                                                                                                                                                                                                                        | Must have  |          |                     |
| Nucleus shall send text notifications (to phones) based on predefined events and based on user roles.                                                                                                                                                                                                                                                                             | Must have  |          |                     |
| Nucleus shall send notifications to administrators and other related recipients on resource consumption above a threshold value, data pipeline failures, component crash events, too many failed login attempts (above a threshold value) for a single user, no progress in a data pipeline for a long time (above a threshold value) and any other interesting patterns in logs. | Must have  |          |                     |
| Nucleus shall send notifications to data pipeline users (customers) on data pipeline completions and data pipeline failures                                                                                                                                                                                                                                                       | Must have  |          |                     |

## Scalability and Performance Requirements

| Requirement                                                                                                                                                               | Importance | Priority | Rationale / Comment |
|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------|----------|---------------------|
| Nucleus shall provide horizontal scalability.                                                                                                                             | Must have  |          |                     |
| Nucleus shall upscale and downscale automatically based on the load and resource consumption.                                                                             | Must have  |          |                     |
| Nucleus shall plug vertically scalable processing nodes which are capable of processing CPU intensive processes such as machine learning and image processing algorithms. | Must have  |          |                     |
| Nucleus shall define caps/thresholds for resource consumption levels                                                                                                      | Must have  |          |                     |
| Any processing node of Nucleus shall not consume more than xx% of the available CPU of any processing node.                                                               | Must have  |          |                     |
| Any processing node of Nucleus shall not consume more than xx% of the available memory (RAM) of any processing node.                                                      | Must have  |          |                     |
| The response time of any of the operations of the RESTful API of Nucleus shall not exceed xxxx milliseconds.                                                              | Must have  |          |                     |
| The response time of any of the operations of the CLI of Nucleus shall not exceed xxxx milliseconds.                                                                      | Must have  |          |                     |
| Nucleus data pipelines shall process data volumes of at least xxx Gigabytes in size (for each data pipeline execution).                                                   | Must have  |          |                     |
| A Nucleus data pipeline shall have at least N processing nodes.                                                                                                           | Must have  |          |                     |
| A Nucleus data pipeline shall execute at least N parallel branches in a single data pipeline concurrently.                                                                | Must have  |          |                     |
| A Nucleus data pipeline shall execute at least N parallel data pipelines concurrently.                                                                                    | Must have  |          |                     |
| Any single node failure/overload in Nucleus should not result in a system overload                                                                                        | Must have  |          |                     |

## Availability Requirements

| Requirement                                                                                                                | Importance | Priority | Rationale / Comment |
|----------------------------------------------------------------------------------------------------------------------------|------------|----------|---------------------|
| Nucleus shall maintain 99.99% availability, where, Availability = (Planned Uptime - Unplanned Downtime) ÷ (Planned Uptime) | Must have  |          |                     |

Security Requirements

## Authentication and Authorization

| Requirement                                                                                                                                                                                                                                                               | Importance | Priority | Rationale / Comment |
|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------|----------|---------------------|
| Nucleus shall support pluggable authentication and authorization mechanisms.                                                                                                                                                                                              | Must have  |          |                     |
| Nucleus shall provide role-based permissions to restrict data pipeline authoring, data pipeline management and data pipeline execution. These restrictions shall be applicable to the operations invoked through other interfaces of Nucleus such as RESTful API and CLI. | Must have  |          |                     |
| Data passes through Nucleus shall only be accessible by authorized users/services.                                                                                                                                                                                        | Must have  |          |                     |

## User, Role and Permission Management

| Requirement                                                                                        | Importance | Priority | Rationale / Comment |
|----------------------------------------------------------------------------------------------------|------------|----------|---------------------|
| Nucleus shall have a pluggable User Management module to manage Users, User Roles and Permissions. | Must have  |          |                     |
| Nucleus User Management module shall create, update and delete Users.                              | Must have  |          |                     |
| Nucleus User Management module shall create, update and delete User Roles.                         | Must have  |          |                     |
| Nucleus User Management module shall create, update and delete Permissions.                        | Must have  |          |                     |
| Nucleus User Management module shall add multiple Permissions to a User Role.                      | Must have  |          |                     |
| Nucleus User Management module shall add multiple Roles to a User.                                 | Must have  |          |                     |

## Cost Optimization Requirements

| Requirement                                                                              | Importance | Priority | Rationale / Comment |
|------------------------------------------------------------------------------------------|------------|----------|---------------------|
| Nucleus shall execute data pipelines on cost optimized infrastructure wherever possible. | Must have  |          |                     |
| Nucleus shall execute data pipelines in cost optimized timeframes whenever possible.     | Must have  |          |                     |

## Platform Requirements

| Requirement                             | Importance | Priority | Rationale / Comment |
|-----------------------------------------|------------|----------|---------------------|
| Nucleus shall operate on the AWS cloud. | Must have  |          |                     |
