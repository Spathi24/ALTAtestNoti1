# monday.com API Reference — Consolidated Local Copy

Generated from public monday.com developer documentation.

Pages included: 42

---

# How to access the dashboard

Source: https://developer.monday.com/api-reference/docs/api-analytics

The API analytics dashboard helps you manage your API usage by tracking your account's daily usage, trends, and top contributors. The dashboard is currently only available for Enterprise account admins.

monday.com accounts are subject to a
daily API call limit
. This limit restricts the number of API calls each account can make in a given day based on its plan tier. It helps reduce the load on the API, ensuring it remains a free feature across all plans while also controlling operational costs.

The API analytics dashboard is accessible from both the
Developer Center
and the
Admin
tab:


## Developer Center

- Open the
Developer Center
.
- Click
API analytics
.

## Admin tab

- Click on your profile picture in the top-right corner.
- Select
Administration
.
- Navigate to
Usage stats
in the left-side menu.
- Click
API
.
The API analytics dashboard contains the widgets below. The data refreshes approximately every 10 minutes.


## Current API usage

The
Current API usage
widget shows the number of calls made in a given day toward the account's
daily limit
. This count includes all calls made by individual users and apps. Tracking your API usage helps you understand how many calls are remaining before exceeding the limit.


## Daily API usage trends

The
Daily API usage trends
widget tracks your account's API usage over the past 14 days. This data provides insights into consumption patterns which can help identify trends, forecast future usage, and optimize API calls accordingly.


## API usage by top users

The API usage by top users widget lists the top six users who made the most API calls in the past 14 days, including calls made through applications on their behalf. This data helps identify specific users contributing to the account's API usage, ultimately helping to manage the daily call limit more effectively.


## API usage by top apps

The
API usage by top apps
widget lists the top six applications that made the most API calls in the past 14 days. This data shows each app's relative contribution to overall API usage, ultimately helping you identify which apps are consuming the most.

Updated
7 months ago


---

# API SDK

Source: https://developer.monday.com/api-reference/docs/api-sdk

The API SDK simplifies interactions with monday.com's GraphQL platform API, making it easier than ever to get started! It replaces complex GraphQL queries by providing simple operations for common endpoints, like retrieving boards or creating items.

It is supported in Node.js and browser environments and uses the graphql-request client under the hood. You can access the API SDK
here
.

Updated
about 1 month ago


---

# Version types

Source: https://developer.monday.com/api-reference/docs/api-versioning

Versioning is an important approach to continuously evolve our API without disrupting existing functionality. It enables developers to make updates and improvements while maintaining a stable and predictable behavior.

We guarantee at least
three
different versions of the API in parallel and release a new version every quarter. You can read more about the latest versions in our
release notes
.

The current versions are:

There are at least three types of API versions at any given time: release candidate, current, and maintenance. Two are
stable
, and the other is an
unstable
preview version.

This guarantees that any given version will be stable for
at least six months
. You can minimize your development effort by always passing a
version header
with your API calls.


| Type | Description |
| --- | --- |
| Release candidate (RC) | Provides early access to the latest features and improvements
Unstable
and should not be used in production applications
Previously known as the
Preview version |
| Current | Only bug fixes with no breaking changes
Stable
and can be used in production applications
Used as the default version when no header is passed
Anything built using this won't change for at least six months
Previously known as the
Stable version |
| Maintenance | Only bug fixes with no breaking changes
Stable
and can be used in production applications (recommended to only use it when you are unable to migrate to the
current
version on time)
Previously known as the
Deprecated version |

Type

Description

Release candidate (RC)

- Provides early access to the latest features and improvements
- Unstable
and should not be used in production applications
- Previously known as the
Preview version
Current

- Only bug fixes with no breaking changes
- Stable
and can be used in production applications
- Used as the default version when no header is passed
- Anything built using this won't change for at least six months
- Previously known as the
Stable version
Maintenance

- Only bug fixes with no breaking changes
- Stable
and can be used in production applications (recommended to only use it when you are unable to migrate to the
current
version on time)
- Previously known as the
Deprecated version

## Documentation

Our
guides
and
API reference
will always reflect the schema of the
current version
. All upcoming updates or schema changes will be announced in the

API changelog
and
release notes
and denoted in the API reference when relevant (see the example below).

Each version moves through the following lifecycle:

- Release a new
RC
(every quarter)
- RC
-->
Current
(after 3 months)
- Current
-->
Maintenance
(after 3 months)
- Maintenance
-->
Deprecated
(will be announced
at least
6 months in advance)

## Release schedule

New RCs are gradually released every three months at the start of each quarter at 12:00 AM UTC.

Version names are not semantic but instead refer to the year and month in which they become the default/current version.
For example
, the July/Q3 2024 current version would be called
2024-07
.


| Version name | RC | Current (default) | Maintenance | Deprecated |
| --- | --- | --- | --- | --- |
| 2024-10 | July 1st, 2024 | October 1st, 2024 | January 15th, 2025 | February 15th, 2026 |
| 2025-01 | October 1st, 2024 | January 15th, 2025 | April 1st, 2025 | February 15th, 2026 |
| 2025-04 | January 15th, 2025 | April 1st, 2025 | July 1st, 2025 | Not yet announced* |
| 2025-07 | April 1st, 2025 | July 1st, 2025 | October 1st, 2025 | Not yet announced* |
| 2025-10 | July 1st, 2025 | October 1st, 2025 | January 15th, 2026 | Not yet announced* |
| 2026-01 | October 1st, 2025 | January 15th, 2026 | April 1st, 2026 | Not yet announced* |
| 2026-04 | January 15th, 2026 | April 1st, 2026 | July 1st, 2026 | Not yet announced* |
| 2026-07 | April 1st, 2026 | July 1st, 2026 | October 1st, 2026 | Not yet announced* |

*Each version deprecation will be announced at least six months in advance!

You can access different versions of the API using a header in an HTTP request, through the SDK, or in the API playground.


### Passing the version name in your request

We strongly encourage production applications to pass a
version name
in each API call. If you don't, your app will always get the
Current version
. Passing a version name makes your app less susceptible to breaking changes and gives you more time to migrate to a new version.


## Using the
API-Version
header in an HTTP request

You can select which API version you want to use by sending the version name in the
API-Version
header.


```graphql
fetch ("https://api.monday.com/v2", {
  method: 'post',
  headers: {
    'Content-Type': 'application/json',
    'Authorization' : 'YOUR_API_KEY_HERE',
    'API-Version' : '2025-07'
   },
   body: JSON.stringify({
     'query' : 'query{version {kind value} }'
   })
  });
```

fetch ("https://api.monday.com/v2", {
  method: 'post',
  headers: {
    'Content-Type': 'application/json',
    'Authorization' : 'YOUR_API_KEY_HERE',
    'API-Version' : '2025-07'
   },
   body: JSON.stringify({
     'query' : 'query{version {kind value} }'
   })
  });


```graphql
curl --location --request POST 'https://api.monday.com/v2' \
--header 'API-Version: 2024-01' \
--header 'Authorization: YOUR_API_KEY_HERE' \
--header 'Content-Type: application/json' \
--data-raw '{"query":"query { version { kind value } }"}'
```

curl --location --request POST 'https://api.monday.com/v2' \
--header 'API-Version: 2024-01' \
--header 'Authorization: YOUR_API_KEY_HERE' \
--header 'Content-Type: application/json' \
--data-raw '{"query":"query { version { kind value } }"}'

All API responses include the
API-Version
header to indicate the version used during the call, or you can query the
version
object to return the same data. If you'd like to see all available API versions, you can query the
versions
object.


## Using the SDK

We support two ways to set the API version when using the
GraphQL JS SDK
: setting the default version or passing the version for a specific call.


```graphql
import { ApiClient } from "@mondaydotcomorg/api";

const monday = new ApiClient({
  token: process.env.MONDAY_API_TOKEN,  // required
  version: "2024-01"                    // sets default API version
});
```

import { ApiClient } from "@mondaydotcomorg/api";

const monday = new ApiClient({
  token: process.env.MONDAY_API_TOKEN,  // required
  version: "2024-01"                    // sets default API version
});


```graphql
const query = `query { me { id } }`;

const data = await monday.request(query, {
  version: "2024-01"
});
```

const query = `query { me { id } }`;

const data = await monday.request(query, {
  version: "2024-01"
});


## API playground

You can also use the
API playground
to access and test different versions of the API by clicking the
clock going in reverse
icon in the middle of the screen.

This will open the version selector where you can test queries and mutations with any of the versions listed.

Versioning is a powerful way to improve the API, but understanding which version to request and when can be confusing. We've compiled these hypothetical scenarios to help you better understand the flow!

- We announce the release of a new API called
new_API
in version
2024-01
. You can access
new_API
as soon as
2024-01
is released as the
RC
by passing
2024-01
in the
API-Version
header. If you don't include the
API-Version
header, it will automatically call the
Current version
and you will get an error stating that the field does not exist.
- We announce the deprecation of the
example
field in version
2023-07
. You can access the
example
field until January 15th, 2024 when
2023-07
is deprecated. Once you start passing
2024-04
in your request, you will no longer have access to the
example
field.
API versioning differs across the board, so frequently used terms may mean something slightly different in each case. This section walks through some of the most important concepts and terms we use, and more importantly, covers exactly what they mean!


| Term | Description |
| --- | --- |
| Stable | Indicates that a version can reliably be used in production. Addresses only non-breaking bug fixes, regressions, and critical bugs that require breaking changes. |
| Default | The version that will be called when no header or the
default
header is passed in an API call. |
| Unstable | Indicates that a version cannot reliably be used in production. Addresses both breaking and non-breaking changes. |
| Deprecated | Indicates that a version is no longer supported. Any calls made to a deprecated version will use the
Maintenance version. |
| Version name | The version's unique identifier (e.g.,
2023-10
). We recommend passing the version name in your calls. |
| Version type | The type of version:
release-candidate
,
current
, or
maintenance
. |

Have questions about versioning? Have no fear! Keep reading to learn more about common issues below and how to resolve them.


## Unsupported versions

- Any request to a version of the API that has been deprecated will get the
Maintenance version
. If you request a version that does not exist (e.g.,
2024-02
instead of
2024-01
), you will get the
Current version.

## Invalid requests

- You will get an
InvalidVersionException
error if your request is not formatted properly (e.g.
2023
instead of
2023-04
). Refer to our
release schedule
to see all version names and ensure they are properly formatted in your call.
- If you make an API call using a field that doesn't exist in a specific version, you will get an error stating that the field does not exist (see below). Make sure you're accessing the updated version by passing the version name in your call!

```graphql
{
  "errors": [
    {
      "message": "Field 'new_field' doesn't exist on type 'Boards'",
      "locations": [
        {
          "line": 4,
          "column": 5
        }
      ],
      "path": [
        "query",
        "boards",
        "new_field"
      ],
      "extensions": {
        "code": "undefinedField",
        "typeName": "Boards",
        "fieldName": "new_field"
      }
    }
  ],
  "account_id": 1
}
```

{
  "errors": [
    {
      "message": "Field 'new_field' doesn't exist on type 'Boards'",
      "locations": [
        {
          "line": 4,
          "column": 5
        }
      ],
      "path": [
        "query",
        "boards",
        "new_field"
      ],
      "extensions": {
        "code": "undefinedField",
        "typeName": "Boards",
        "fieldName": "new_field"
      }
    }
  ],
  "account_id": 1
}

Updated
23 days ago


---

# App installs

Source: https://developer.monday.com/api-reference/docs/app-installs

Updated
2 months ago

Updated
2 months ago


---

# Token permissions

Source: https://developer.monday.com/api-reference/docs/authentication

The monday.com platform API utilizes
personal V2 API tokens
to authenticate requests and identify the user making the call. These tokens are unique to each user and have no explicit length.

Personal tokens allow you to interact with the API using your own user account. Their permissions mirror what you can do in the monday.com UI, ensuring that API access is consistent with your platform-level permissions.

Personal tokens mirror all permission levels set in the monday.com UI, including
board
,
column
,
item
, or
account
access.

For example: If you don't have permission to access a certain workspace via the UI, you won't have permission using your personal API token either.

App tokens have an additional
set of permission scopes
that specify which queries and mutations it can access, while personal tokens have all permission scopes.

You can access your API token in two ways, depending on your
user type
.


## In the Developer Center (all users)

All
users with API access
can follow these steps to access their API token:

- In your monday.com account, click on your profile picture in the top right corner.
- Select
Developers
. This will open the
Developer Center
in another tab.
- Click
API token
>
Show
.
- Copy your personal token.

## In the Administration tab (account admins only)

Account admins can use the
Developer Center
steps above or access their token via the
Administration
tab:

- In your monday.com account, click on your profile picture in the top right corner.
- Select
Administration
>
Connections
>
Personal API token
.
- Copy your personal token.
Once you have your token, you can make requests with the API by passing the token in the
Authorization
header.


```graphql
curl -X POST https://api.monday.com/v2 \
  -H "Authorization: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{"query": "query { me { id name } }"}'
```

curl -X POST https://api.monday.com/v2 \
  -H "Authorization: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{"query": "query { me { id name } }"}'

API tokens can be regenerated at any time. However, this will immediately invalidate your current token, so be sure to update any integrations using it.


## How to regenerate a token


### In the Developer Center

- In your monday.com account, click on your profile picture in the top right corner.
- Select
Developers
. This will open the
Developer Center
in another tab.
- Click
API token
>
Regenerate
.

### In the Administration tab

- In your monday.com account, click on your profile picture in the top right corner.
- Select
Administration
>
Connections
>
Personal API token
.
- Click
Regenerate
.
Updated
7 months ago


---

# Why use the API?

Source: https://developer.monday.com/api-reference/docs/basics

Welcome to monday.com, a work OS where teams create and shape their own workflows in minutes, code-free. Our mission is to help teams outdo their best, fulfilling their potential, and collaborating more effectively.

The monday GraphQL API is part of the
monday apps framework
. It is an application layer that allows apps to read and update data inside a monday.com account. It supports operations boards, items, column values, users, workspaces, and more.

There are countless use cases for the API, including:

- Accessing board data to render a custom report inside a monday.com dashboard
- Creating a new item on a board when a record is created on another system
- Importing data from another source programmatically
With the monday apps framework, developers can package their own web apps and integrations as native monday.com building blocks.

Admin
,
member
, and
guest
users are all able to utilize the monday.com API.

Admins
and
members
have access to their own
API tokens
.
Guests
cannot access an API key but can utilize API features through other authentication methods, like OAuth or a shortLivedToken.

Viewers
, users who have been deactivated or disabled, users with unconfirmed emails, or users on student accounts
cannot
access the API.

The platform API currently supports the monday work management, dev, sales CRM, and service products. It currently does not support Workforms.

The monday.com API is built with GraphQL, a flexible query language that allows you to return as much or as little data as you need. GraphQL is an application layer that parses the query you send it and returns (or changes) data accordingly. To learn more about the fundamental GraphQL components, check out our
GraphQL overview
!


### Join our developer community!

We've created a
community
specifically for our devs where you can search through previous topics to find solutions, ask new questions, hear about new features and updates, and learn tips and tricks from other devs. Come join in on the fun! 😎

Updated
21 days ago


---

# Blocks

Source: https://developer.monday.com/api-reference/docs/blocks

Updated
about 1 month ago

Updated
about 1 month ago


---

# Boards

Source: https://developer.monday.com/api-reference/docs/boards

Updated
about 1 month ago

Updated
about 1 month ago


---

# Complexity

Source: https://developer.monday.com/api-reference/docs/complexity

Updated
2 months ago

Updated
2 months ago


---

# Error format

Source: https://developer.monday.com/api-reference/docs/error-handling

If your API request cannot be completed successfully, you will receive an error message.

Errors returned by the API have the following characteristics:

- HTTP status:
Response will be
200 – OK
for application-level errors. Other statuses will be returned for transport-layer errors, such as
500 - Internal server error
,
429 - Too many requests
or
400 - Bad request
- JSON response:
Body will contain an
errors
array with further details about each error
- Partial data:
Requests will return partial data, so the
data
object may also contain some information. For example, if you query three fields, you may receive two fields and one error.
- Retry-After
header:
Errors will include the
Retry-After
header to indicate how long you need to wait before making another request
- Each API response includes a
request_id
in the extensions object that can be used for troubleshooting.

### Sample format

Here's an example of an application-level error:


```graphql
{
  "data" : [],
  "errors": [
    {
      "message": "User unauthorized to perform action",
      "locations": [
        {
          "line": 2,
          "column": 3
        }
      ],
      "path": [
        "me"
      ],
      "extensions": {
        "code": "UserUnauthorizedException",
        "error_data": {},
        "status_code": 403
      }
    }
  ],
  "account_id": 123456
}
```

{
  "data" : [],
  "errors": [
    {
      "message": "User unauthorized to perform action",
      "locations": [
        {
          "line": 2,
          "column": 3
        }
      ],
      "path": [
        "me"
      ],
      "extensions": {
        "code": "UserUnauthorizedException",
        "error_data": {},
        "status_code": 403
      }
    }
  ],
  "account_id": 123456
}


```graphql
{
  "data": {
    "me": {
      "id": "4012689",
      "photo_thumb": null
    },
    "complexity": {
      "query": 12
    }
  },
  "errors": [
    {
      "message": "Photo unavailable.",
      "locations": [
        {
          "line": 4,
          "column": 5
        }
      ],
      "path": [
        "me",
        "photo_thumb"
       ],
      "extensions": {
        "code": "ASSET_UNAVAILABLE"
      }
    }
  ],
  "account_id": 18888528
}
```

{
  "data": {
    "me": {
      "id": "4012689",
      "photo_thumb": null
    },
    "complexity": {
      "query": 12
    }
  },
  "errors": [
    {
      "message": "Photo unavailable.",
      "locations": [
        {
          "line": 4,
          "column": 5
        }
      ],
      "path": [
        "me",
        "photo_thumb"
       ],
      "extensions": {
        "code": "ASSET_UNAVAILABLE"
      }
    }
  ],
  "account_id": 18888528
}


## 2xx errors

Errors with a 2xx status code indicate that monday.com is not accepting the requested action due to a platform restriction, limitation, or rule. These errors occur for various reasons, including passing invalid values, missing permissions, or reaching character limits.

Here are
some
of the most common errors:


| Error code | HTTP status code | Description | Resolution |
| --- | --- | --- | --- |
| API_TEMPORARILY_BLOCKED | 200 | There is an issue with the API and usage has temporarily been blocked | Check the
status page
for updates and retry your call once the issue has been resolved. |
| ColumnValueException | 200 | Incorrect column value formatting | Ensure the
column
is supported by our API and not calculated in the client.
Verify that the column value conforms with each
column's data structure
.
Check that the
connect boards column
you're referencing is connected to a board via the monday.com UI. |
| CorrectedValueException | 200 | The query is of the wrong type | If you try to update a column with simple values (
String
values), ensure the column supports this type of value format. |
| CreateBoardException | 200 | Error in your create board mutation | If you’re creating a board from a template, ensure the template ID is a valid monday template or a board that has template status. To learn more about making a board a template, check out our resource on board templates
here
.
If you’re duplicating a board, ensure the board ID exists. |
| InvalidArgumentException | 200 | The argument being passed in the query is invalid, you've hit a pagination limit, you're querying a subitem board ID, or a board ID is not found | Check your argument for typos.
Verify that the argument exists for the object you are querying.
Make your result window smaller. |
| InvalidBoardIdException | 200 | The board ID being passed in the query is invalid | Verify that the board ID exists and that you have access to it. |
| InvalidColumnIdException | 200 | The column ID being passed in the query is invalid | Verify that the column ID exists and that you have access to it. |
| InvalidUserIdException | 200 | The user ID being passed in the query is invalid | Verify that the user ID exists and that the user is assigned to your board. |
| InvalidVersionException | 200 | The requested API version is invalid | Ensure that your request follows the proper
format
. |
| ItemNameTooLongException | 200 | The item name has exceeded the allotted number of characters | Ensure the item name is 1-255 characters in length. |
| ItemsLimitationException | 200 | You have exceeded the limit of 10,000 items per board | Reduce the number of items on the board. |
| missingRequiredPermissions | 200 | The operation has exceeded the OAuth permission scopes granted for the app | Review your app's
permission scopes
to ensure the correct ones are requested. |
| Parse error on... | 200 | Incorrect query string formatting | Verify that all strings are valid in your query.
Close all parentheses, brackets, and curly brackets. |
| ResourceNotFoundException | 200 | The ID being passed in your query is invalid | Verify that the ID of the item, group, or board you’re querying exists. |

Error code

HTTP status code

Description

Resolution

API_TEMPORARILY_BLOCKED

200

There is an issue with the API and usage has temporarily been blocked

Check the
status page
for updates and retry your call once the issue has been resolved.

ColumnValueException

200

Incorrect column value formatting

- Ensure the
column
is supported by our API and not calculated in the client.
- Verify that the column value conforms with each
column's data structure
.
- Check that the
connect boards column
you're referencing is connected to a board via the monday.com UI.
CorrectedValueException

200

The query is of the wrong type

If you try to update a column with simple values (
String
values), ensure the column supports this type of value format.

CreateBoardException

200

Error in your create board mutation

- If you’re creating a board from a template, ensure the template ID is a valid monday template or a board that has template status. To learn more about making a board a template, check out our resource on board templates
here
.
- If you’re duplicating a board, ensure the board ID exists.
InvalidArgumentException

200

The argument being passed in the query is invalid, you've hit a pagination limit, you're querying a subitem board ID, or a board ID is not found

- Check your argument for typos.
- Verify that the argument exists for the object you are querying.
- Make your result window smaller.
InvalidBoardIdException

200

The board ID being passed in the query is invalid

Verify that the board ID exists and that you have access to it.

InvalidColumnIdException

200

The column ID being passed in the query is invalid

Verify that the column ID exists and that you have access to it.

InvalidUserIdException

200

The user ID being passed in the query is invalid

Verify that the user ID exists and that the user is assigned to your board.

InvalidVersionException

200

The requested API version is invalid

Ensure that your request follows the proper
format
.

ItemNameTooLongException

200

The item name has exceeded the allotted number of characters

Ensure the item name is 1-255 characters in length.

ItemsLimitationException

200

You have exceeded the limit of 10,000 items per board

Reduce the number of items on the board.

missingRequiredPermissions

200

The operation has exceeded the OAuth permission scopes granted for the app

Review your app's
permission scopes
to ensure the correct ones are requested.

Parse error on...

200

Incorrect query string formatting

- Verify that all strings are valid in your query.
- Close all parentheses, brackets, and curly brackets.
ResourceNotFoundException

200

The ID being passed in your query is invalid

Verify that the ID of the item, group, or board you’re querying exists.


## 4xx client errors

Errors with a 4xx status code indicate that something went wrong on the client's (your) side. These errors occur for various reasons, including a lack of access to the requested information, excessive use of the API, or providing incorrect input.

Here are
some
of the most common errors:


| Error | HTTP status code | Description | Resolution |
| --- | --- | --- | --- |
| Bad request | 400 | The structure of your query string was passed incorrectly | Pass your query string with the
query
key.
Send your request as a POST request with a JSON body.
Avoid unterminated strings in your query. |
| JsonParseException | 400 | Issues interpreting the provided JSON | Verify all JSON is valid using a JSON validator (e.g.,
JSON lint
) |
| Unauthorized | 401 | You don't have permission to access the data | Input a valid API key.
Pass the key in the
Authorization
header. |
| Your ip is restricted | 401 | An account admin has restricted access to the system from specific IP addresses | Confirm that your IP address is not restricted by your account admin. |
| UserUnauthorizedException | 403 | The user doesn't have the required permission to perform the action in question | Verify that the user has permission to access or edit the given resource. |
| USER_ACCESS_DENIED | 403 | The user is unauthorized to use the API | Verify that the user is active, not view-only, and has a confirmed email address. |
| ResourceNotFoundException | 404 | The ID being passed in the query is invalid | Verify that the ID of the user you are querying exists and is assigned to your board. |
| DeleteLastGroupException | 409 | The last group on a board is being deleted or archived | Verify that you have at least one group on the board. |
| RecordInvalidException | 422 | Indicates one of the following:
A board has exceeded 400 individual subscribers or 100 team subscribers
A user or team has subscribed to more than 10,000 boards | Learn how to
optimize board subscribers
.
Unsubscribe from, delete, or archive irrelevant boards. |
| Resource is currently locked, please try again later | 423 | The board is temporarily locked because another process is performing a concurrent update (e.g., column update, automation). During this time, write operations are blocked to ensure data consistency. | Retry the request after a short delay.
Avoid concurrent updates to the same board from multiple sources. |
| maxConcurrencyExceeded | 429 | You exceeded the maximum number of queries allowed at once | Reduce the number of queries sent at once.
Use a retry mechanism in your code. |
| Rate Limit Exceeded | 429 | You made more than 5,000 requests in one minute | Reduce the number of requests sent in one minute. |
| COMPLEXITY_BUDGET_EXHAUSTED | 429 | You have reached the complexity limit | Utilize the
limits
and
page
arguments.
Only request the information you need.
Read more about
rate limits
. |
| IP_RATE_LIMIT_EXCEEDED | 429 | You have reached the
IP limit | Wait for the specified period in the error response before retrying your call.
Learn about
optimizing your API usage
. |

Error

HTTP status code

Description

Resolution

Bad request

400

The structure of your query string was passed incorrectly

- Pass your query string with the
query
key.
- Send your request as a POST request with a JSON body.
- Avoid unterminated strings in your query.
JsonParseException

400

Issues interpreting the provided JSON

Verify all JSON is valid using a JSON validator (e.g.,
JSON lint
)

Unauthorized

401

You don't have permission to access the data

- Input a valid API key.
- Pass the key in the
Authorization
header.
Your ip is restricted

401

An account admin has restricted access to the system from specific IP addresses

Confirm that your IP address is not restricted by your account admin.

UserUnauthorizedException

403

The user doesn't have the required permission to perform the action in question

Verify that the user has permission to access or edit the given resource.

USER_ACCESS_DENIED

403

The user is unauthorized to use the API

Verify that the user is active, not view-only, and has a confirmed email address.

ResourceNotFoundException

404

The ID being passed in the query is invalid

Verify that the ID of the user you are querying exists and is assigned to your board.

DeleteLastGroupException

409

The last group on a board is being deleted or archived

Verify that you have at least one group on the board.

RecordInvalidException

422

Indicates one of the following:

- A board has exceeded 400 individual subscribers or 100 team subscribers
- A user or team has subscribed to more than 10,000 boards
- Learn how to
optimize board subscribers
.
- Unsubscribe from, delete, or archive irrelevant boards.
Resource is currently locked, please try again later

423

The board is temporarily locked because another process is performing a concurrent update (e.g., column update, automation). During this time, write operations are blocked to ensure data consistency.

- Retry the request after a short delay.
- Avoid concurrent updates to the same board from multiple sources.
maxConcurrencyExceeded

429

You exceeded the maximum number of queries allowed at once

- Reduce the number of queries sent at once.
- Use a retry mechanism in your code.
Rate Limit Exceeded

429

You made more than 5,000 requests in one minute

Reduce the number of requests sent in one minute.

COMPLEXITY_BUDGET_EXHAUSTED

429

You have reached the complexity limit

- Utilize the
limits
and
page
arguments.
- Only request the information you need.
- Read more about
rate limits
.
IP_RATE_LIMIT_EXCEEDED

429

You have reached the
IP limit

- Wait for the specified period in the error response before retrying your call.
- Learn about
optimizing your API usage
.

## 5xx server errors

Errors with a 5xx status code indicate that something went wrong on the server's (monday's) side.

Here are
some
of the most common errors:


| Error | HTTP status code | Description | Resolution |
| --- | --- | --- | --- |
| Internal Server Error | 500 | Indicates that something went wrong. Common causes are:
Invalid arguments, such as board or item IDs that don't exist
Malformatted JSON column values | Retry your request after a short period.
Double-check your request's format.
Ensure your API token has the right permissions. |

Error

HTTP status code

Description

Resolution

Internal Server Error

500

Indicates that something went wrong. Common causes are:

- Invalid arguments, such as board or item IDs that don't exist
- Malformatted JSON column values
- Retry your request after a short period.
- Double-check your request's format.
- Ensure your API token has the right permissions.

### Join our developer community!

We've created a
community
specifically for our devs where you can search through previous topics to find solutions, ask new questions, hear about new features and updates, and learn tips and tricks from other devs. Come join in on the fun! 😎

Updated
6 months ago


---

# Error format

Source: https://developer.monday.com/api-reference/docs/errors

If your API request cannot be completed successfully, you will receive an error message.

Errors returned by the API have the following characteristics:

- HTTP status:
Response will be
200 – OK
for application-level errors. Other statuses will be returned for transport-layer errors, such as
500 - Internal server error
,
429 - Too many requests
or
400 - Bad request
- JSON response:
Body will contain an
errors
array with further details about each error
- Partial data:
Requests will return partial data, so the
data
object may also contain some information. For example, if you query three fields, you may receive two fields and one error.
- Retry-After
header:
Errors will include the
Retry-After
header to indicate how long you need to wait before making another request
- Each API response includes a
request_id
in the extensions object that can be used for troubleshooting.

### Sample format

Here's an example of an application-level error:


```graphql
{
  "data" : [],
  "errors": [
    {
      "message": "User unauthorized to perform action",
      "locations": [
        {
          "line": 2,
          "column": 3
        }
      ],
      "path": [
        "me"
      ],
      "extensions": {
        "code": "UserUnauthorizedException",
        "error_data": {},
        "status_code": 403
      }
    }
  ],
  "account_id": 123456
}
```

{
  "data" : [],
  "errors": [
    {
      "message": "User unauthorized to perform action",
      "locations": [
        {
          "line": 2,
          "column": 3
        }
      ],
      "path": [
        "me"
      ],
      "extensions": {
        "code": "UserUnauthorizedException",
        "error_data": {},
        "status_code": 403
      }
    }
  ],
  "account_id": 123456
}


```graphql
{
  "data": {
    "me": {
      "id": "4012689",
      "photo_thumb": null
    },
    "complexity": {
      "query": 12
    }
  },
  "errors": [
    {
      "message": "Photo unavailable.",
      "locations": [
        {
          "line": 4,
          "column": 5
        }
      ],
      "path": [
        "me",
        "photo_thumb"
       ],
      "extensions": {
        "code": "ASSET_UNAVAILABLE"
      }
    }
  ],
  "account_id": 18888528
}
```

{
  "data": {
    "me": {
      "id": "4012689",
      "photo_thumb": null
    },
    "complexity": {
      "query": 12
    }
  },
  "errors": [
    {
      "message": "Photo unavailable.",
      "locations": [
        {
          "line": 4,
          "column": 5
        }
      ],
      "path": [
        "me",
        "photo_thumb"
       ],
      "extensions": {
        "code": "ASSET_UNAVAILABLE"
      }
    }
  ],
  "account_id": 18888528
}


## 2xx errors

Errors with a 2xx status code indicate that monday.com is not accepting the requested action due to a platform restriction, limitation, or rule. These errors occur for various reasons, including passing invalid values, missing permissions, or reaching character limits.

Here are
some
of the most common errors:


| Error code | HTTP status code | Description | Resolution |
| --- | --- | --- | --- |
| API_TEMPORARILY_BLOCKED | 200 | There is an issue with the API and usage has temporarily been blocked | Check the
status page
for updates and retry your call once the issue has been resolved. |
| ColumnValueException | 200 | Incorrect column value formatting | Ensure the
column
is supported by our API and not calculated in the client.
Verify that the column value conforms with each
column's data structure
.
Check that the
connect boards column
you're referencing is connected to a board via the monday.com UI. |
| CorrectedValueException | 200 | The query is of the wrong type | If you try to update a column with simple values (
String
values), ensure the column supports this type of value format. |
| CreateBoardException | 200 | Error in your create board mutation | If you’re creating a board from a template, ensure the template ID is a valid monday template or a board that has template status. To learn more about making a board a template, check out our resource on board templates
here
.
If you’re duplicating a board, ensure the board ID exists. |
| InvalidArgumentException | 200 | The argument being passed in the query is invalid, you've hit a pagination limit, you're querying a subitem board ID, or a board ID is not found | Check your argument for typos.
Verify that the argument exists for the object you are querying.
Make your result window smaller. |
| InvalidBoardIdException | 200 | The board ID being passed in the query is invalid | Verify that the board ID exists and that you have access to it. |
| InvalidColumnIdException | 200 | The column ID being passed in the query is invalid | Verify that the column ID exists and that you have access to it. |
| InvalidUserIdException | 200 | The user ID being passed in the query is invalid | Verify that the user ID exists and that the user is assigned to your board. |
| InvalidVersionException | 200 | The requested API version is invalid | Ensure that your request follows the proper
format
. |
| ItemNameTooLongException | 200 | The item name has exceeded the allotted number of characters | Ensure the item name is 1-255 characters in length. |
| ItemsLimitationException | 200 | You have exceeded the limit of 10,000 items per board | Reduce the number of items on the board. |
| missingRequiredPermissions | 200 | The operation has exceeded the OAuth permission scopes granted for the app | Review your app's
permission scopes
to ensure the correct ones are requested. |
| Parse error on... | 200 | Incorrect query string formatting | Verify that all strings are valid in your query.
Close all parentheses, brackets, and curly brackets. |
| ResourceNotFoundException | 200 | The ID being passed in your query is invalid | Verify that the ID of the item, group, or board you’re querying exists. |

Error code

HTTP status code

Description

Resolution

API_TEMPORARILY_BLOCKED

200

There is an issue with the API and usage has temporarily been blocked

Check the
status page
for updates and retry your call once the issue has been resolved.

ColumnValueException

200

Incorrect column value formatting

- Ensure the
column
is supported by our API and not calculated in the client.
- Verify that the column value conforms with each
column's data structure
.
- Check that the
connect boards column
you're referencing is connected to a board via the monday.com UI.
CorrectedValueException

200

The query is of the wrong type

If you try to update a column with simple values (
String
values), ensure the column supports this type of value format.

CreateBoardException

200

Error in your create board mutation

- If you’re creating a board from a template, ensure the template ID is a valid monday template or a board that has template status. To learn more about making a board a template, check out our resource on board templates
here
.
- If you’re duplicating a board, ensure the board ID exists.
InvalidArgumentException

200

The argument being passed in the query is invalid, you've hit a pagination limit, you're querying a subitem board ID, or a board ID is not found

- Check your argument for typos.
- Verify that the argument exists for the object you are querying.
- Make your result window smaller.
InvalidBoardIdException

200

The board ID being passed in the query is invalid

Verify that the board ID exists and that you have access to it.

InvalidColumnIdException

200

The column ID being passed in the query is invalid

Verify that the column ID exists and that you have access to it.

InvalidUserIdException

200

The user ID being passed in the query is invalid

Verify that the user ID exists and that the user is assigned to your board.

InvalidVersionException

200

The requested API version is invalid

Ensure that your request follows the proper
format
.

ItemNameTooLongException

200

The item name has exceeded the allotted number of characters

Ensure the item name is 1-255 characters in length.

ItemsLimitationException

200

You have exceeded the limit of 10,000 items per board

Reduce the number of items on the board.

missingRequiredPermissions

200

The operation has exceeded the OAuth permission scopes granted for the app

Review your app's
permission scopes
to ensure the correct ones are requested.

Parse error on...

200

Incorrect query string formatting

- Verify that all strings are valid in your query.
- Close all parentheses, brackets, and curly brackets.
ResourceNotFoundException

200

The ID being passed in your query is invalid

Verify that the ID of the item, group, or board you’re querying exists.


## 4xx client errors

Errors with a 4xx status code indicate that something went wrong on the client's (your) side. These errors occur for various reasons, including a lack of access to the requested information, excessive use of the API, or providing incorrect input.

Here are
some
of the most common errors:


| Error | HTTP status code | Description | Resolution |
| --- | --- | --- | --- |
| Bad request | 400 | The structure of your query string was passed incorrectly | Pass your query string with the
query
key.
Send your request as a POST request with a JSON body.
Avoid unterminated strings in your query. |
| JsonParseException | 400 | Issues interpreting the provided JSON | Verify all JSON is valid using a JSON validator (e.g.,
JSON lint
) |
| Unauthorized | 401 | You don't have permission to access the data | Input a valid API key.
Pass the key in the
Authorization
header. |
| Your ip is restricted | 401 | An account admin has restricted access to the system from specific IP addresses | Confirm that your IP address is not restricted by your account admin. |
| UserUnauthorizedException | 403 | The user doesn't have the required permission to perform the action in question | Verify that the user has permission to access or edit the given resource. |
| USER_ACCESS_DENIED | 403 | The user is unauthorized to use the API | Verify that the user is active, not view-only, and has a confirmed email address. |
| ResourceNotFoundException | 404 | The ID being passed in the query is invalid | Verify that the ID of the user you are querying exists and is assigned to your board. |
| DeleteLastGroupException | 409 | The last group on a board is being deleted or archived | Verify that you have at least one group on the board. |
| RecordInvalidException | 422 | Indicates one of the following:
A board has exceeded 400 individual subscribers or 100 team subscribers
A user or team has subscribed to more than 10,000 boards | Learn how to
optimize board subscribers
.
Unsubscribe from, delete, or archive irrelevant boards. |
| Resource is currently locked, please try again later | 423 | The board is temporarily locked because another process is performing a concurrent update (e.g., column update, automation). During this time, write operations are blocked to ensure data consistency. | Retry the request after a short delay.
Avoid concurrent updates to the same board from multiple sources. |
| maxConcurrencyExceeded | 429 | You exceeded the maximum number of queries allowed at once | Reduce the number of queries sent at once.
Use a retry mechanism in your code. |
| Rate Limit Exceeded | 429 | You made more than 5,000 requests in one minute | Reduce the number of requests sent in one minute. |
| COMPLEXITY_BUDGET_EXHAUSTED | 429 | You have reached the complexity limit | Utilize the
limits
and
page
arguments.
Only request the information you need.
Read more about
rate limits
. |
| IP_RATE_LIMIT_EXCEEDED | 429 | You have reached the
IP limit | Wait for the specified period in the error response before retrying your call.
Learn about
optimizing your API usage
. |

Error

HTTP status code

Description

Resolution

Bad request

400

The structure of your query string was passed incorrectly

- Pass your query string with the
query
key.
- Send your request as a POST request with a JSON body.
- Avoid unterminated strings in your query.
JsonParseException

400

Issues interpreting the provided JSON

Verify all JSON is valid using a JSON validator (e.g.,
JSON lint
)

Unauthorized

401

You don't have permission to access the data

- Input a valid API key.
- Pass the key in the
Authorization
header.
Your ip is restricted

401

An account admin has restricted access to the system from specific IP addresses

Confirm that your IP address is not restricted by your account admin.

UserUnauthorizedException

403

The user doesn't have the required permission to perform the action in question

Verify that the user has permission to access or edit the given resource.

USER_ACCESS_DENIED

403

The user is unauthorized to use the API

Verify that the user is active, not view-only, and has a confirmed email address.

ResourceNotFoundException

404

The ID being passed in the query is invalid

Verify that the ID of the user you are querying exists and is assigned to your board.

DeleteLastGroupException

409

The last group on a board is being deleted or archived

Verify that you have at least one group on the board.

RecordInvalidException

422

Indicates one of the following:

- A board has exceeded 400 individual subscribers or 100 team subscribers
- A user or team has subscribed to more than 10,000 boards
- Learn how to
optimize board subscribers
.
- Unsubscribe from, delete, or archive irrelevant boards.
Resource is currently locked, please try again later

423

The board is temporarily locked because another process is performing a concurrent update (e.g., column update, automation). During this time, write operations are blocked to ensure data consistency.

- Retry the request after a short delay.
- Avoid concurrent updates to the same board from multiple sources.
maxConcurrencyExceeded

429

You exceeded the maximum number of queries allowed at once

- Reduce the number of queries sent at once.
- Use a retry mechanism in your code.
Rate Limit Exceeded

429

You made more than 5,000 requests in one minute

Reduce the number of requests sent in one minute.

COMPLEXITY_BUDGET_EXHAUSTED

429

You have reached the complexity limit

- Utilize the
limits
and
page
arguments.
- Only request the information you need.
- Read more about
rate limits
.
IP_RATE_LIMIT_EXCEEDED

429

You have reached the
IP limit

- Wait for the specified period in the error response before retrying your call.
- Learn about
optimizing your API usage
.

## 5xx server errors

Errors with a 5xx status code indicate that something went wrong on the server's (monday's) side.

Here are
some
of the most common errors:


| Error | HTTP status code | Description | Resolution |
| --- | --- | --- | --- |
| Internal Server Error | 500 | Indicates that something went wrong. Common causes are:
Invalid arguments, such as board or item IDs that don't exist
Malformatted JSON column values | Retry your request after a short period.
Double-check your request's format.
Ensure your API token has the right permissions. |

Error

HTTP status code

Description

Resolution

Internal Server Error

500

Indicates that something went wrong. Common causes are:

- Invalid arguments, such as board or item IDs that don't exist
- Malformatted JSON column values
- Retry your request after a short period.
- Double-check your request's format.
- Ensure your API token has the right permissions.

### Join our developer community!

We've created a
community
specifically for our devs where you can search through previous topics to find solutions, ask new questions, hear about new features and updates, and learn tips and tricks from other devs. Come join in on the fun! 😎

Updated
6 months ago


---

# Groups

Source: https://developer.monday.com/api-reference/docs/groups

Updated
2 months ago

Updated
2 months ago


---

# Operations

Source: https://developer.monday.com/api-reference/docs/introduction-to-graphql

The monday.com API is built with GraphQL, a flexible query language that allows you to return as much or as little data as you need. It's important to know that GraphQL is an application layer that parses the query you send it and returns (or changes) data accordingly.

Unlike REST APIs, where multiple endpoints return different data, GraphQL always exposes one endpoint and allows you to determine the structure of the returned data. Our API uses the following endpoint:
https://api.monday.com/v2
.

This document will walk through the GraphQL operations and object types to help you understand the essential components of a request. We will also discuss the GraphQL visual interface that enables you to test your queries and mutations, and finally, we cover where you can access the monday.com schema. Let's get started!


### Pro tip

Check out this
introduction to GraphQL
to understand what all you can do with GraphQL!

There are two possible operations in GraphQL:
queries
and
mutations
.


## Query

Queries
perform the READ operation and do not change or alter any data. The result of each query will be formatted in the same way as the query itself. The following example retrieves the ID, title, and type of each column on board 1234567890.


#### Sample query


```graphql
query {
  boards {
    columns {
      id
      title
      type
    }
  }
}
```

query {
  boards {
    columns {
      id
      title
      type
    }
  }
}


#### Sample response


```graphql
{
  "columns": [
    {
      "id": "name",
      "title": "Name",
      "type": "name"
    },
    {
      "id": "subitems",
      "title": "Subitems",
      "type": "subtasks"
    },
    {
      "id": "person",
      "title": "Person",
      "type": "people"
    },
    {
      "id": "status",
      "title": "Status",
      "type": "status"
    }
  ]
}
```

{
  "columns": [
    {
      "id": "name",
      "title": "Name",
      "type": "name"
    },
    {
      "id": "subitems",
      "title": "Subitems",
      "type": "subtasks"
    },
    {
      "id": "person",
      "title": "Person",
      "type": "people"
    },
    {
      "id": "status",
      "title": "Status",
      "type": "status"
    }
  ]
}


## Mutation

Mutations
are special queries that perform the CUD (Create, Update, Delete) operations to modify your data. Mutations return an instance of the object you just modified, so you can query the data you changed. The following example creates a new item on board 1234567890 and returns the ID and name of the new item.


#### Sample mutation


```graphql
mutation{
  create_item (board_id: 1234567890, item_name: "New Item"){
    id
    name
  }
}
```

mutation{
  create_item (board_id: 1234567890, item_name: "New Item"){
    id
    name
  }
}


#### Sample response


```graphql
{
  "data": {
    "create_item": {
      "id": "9876543210",
      "name": "New Item"
    }
  },
  "account_id": 12345678
}
```

{
  "data": {
    "create_item": {
      "id": "9876543210",
      "name": "New Item"
    }
  },
  "account_id": 12345678
}


## Multiple operations in one request

You can also send multiple queries in one request, and they will be executed one after the other. The following query returns the ID and name for boards 1234567890 and 9876543210. The mutation creates a new item and retrieves the item's ID and name on both boards 1234567890 and 9876543210.


#### Sample query


```graphql
query {
  checkBoard1: boards (ids:1234567890) {
    id
    name
  }
  checkBoard2: boards (ids:9876543210) {
    id
    name
  }
}
```

query {
  checkBoard1: boards (ids:1234567890) {
    id
    name
  }
  checkBoard2: boards (ids:9876543210) {
    id
    name
  }
}


#### Sample response


```graphql
{
  "data": {
    "checkBoard1": [
      {
        "id": "1234567890",
        "name": "Test Board 1"
      }
    ],
    "checkBoard2": [
      {
        "id": "9876543210",
        "name": "Test Board 2"
      }
    ]
  },
  "account_id": 12345678
}
```

{
  "data": {
    "checkBoard1": [
      {
        "id": "1234567890",
        "name": "Test Board 1"
      }
    ],
    "checkBoard2": [
      {
        "id": "9876543210",
        "name": "Test Board 2"
      }
    ]
  },
  "account_id": 12345678
}


#### Sample mutation


```graphql
mutation{
  createItem1: create_item (board_id: 1234567890, item_name:"Test Item 1") {
    id
    name
  }
  createItem2: create_item(board_id: 9876543210, item_name:"Test Item 2") {
    id
    name
  }
}
```

mutation{
  createItem1: create_item (board_id: 1234567890, item_name:"Test Item 1") {
    id
    name
  }
  createItem2: create_item(board_id: 9876543210, item_name:"Test Item 2") {
    id
    name
  }
}


#### Sample response


```graphql
{
  "data": {
    "createItem1": {
      "id": "11223344",
      "name": "Test Item 1"
    },
    "createItem2": {
      "id": "44332211",
      "name": "Test Item 2"
    }
  },
  "account_id": 12345678
}
```

{
  "data": {
    "createItem1": {
      "id": "11223344",
      "name": "Test Item 1"
    },
    "createItem2": {
      "id": "44332211",
      "name": "Test Item 2"
    }
  },
  "account_id": 12345678
}

Object types are a collection of fields used to describe the set of possible data you can query using the API. They can also have arguments on the fields to pass parameters when querying data.


## Fields

Fields specify properties or attributes of objects to help define what information to retrieve from a query. Every object in the schema contains fields that can be queried by name to retrieve specific properties of the object.

Take the
boards
object, for example. You can query these
fields
to return specific information about your board(s). The following example returns the boards' ID and name and the ID, title, and type of each column on the boards.


```graphql
query {
  boards {
    id
    name
    columns {
      id
      title
      type
    }
  }
}
```

query {
  boards {
    id
    name
    columns {
      id
      title
      type
    }
  }
}


## Arguments

You can pass arguments in a query to specify what data to return (i.e., filter the search results) and narrow down the results to only the specific ones you’re after.

Building on the
boards
example above, you can also use these
arguments
to reduce the number of results returned in your query. The following example returns the ID and name only for boards 1234567890 and 9876543210 and the ID, title, and type of each column on those boards.


```graphql
query {
  boards (ids: [1234567890, 9876543210]) {
    id
    name
    columns {
      id
      title
      type
    }
  }
}
```

query {
  boards (ids: [1234567890, 9876543210]) {
    id
    name
    columns {
      id
      title
      type
    }
  }
}


### Variables

You can use variables to pass dynamic values to your arguments. They are written outside of the query string itself in the variables section and passed to the arguments.

When we start working with variables, we need to do three things:

- Replace the static value in the query with
$variableName
- Declare
$variableName
as one of the variables accepted by the query
- Pass
variableName: value
in the separate, transport-specific (usually JSON) variables dictionary

```graphql
mutation change_column_value($value: JSON!) {
  change_column_value (board_id: 157244624,item_id: 9539475, column_id: "status", value: $value) {
    id
  }
}

query variables:
{
"value": "{\"index\": 1}"
}
```

mutation change_column_value($value: JSON!) {
  change_column_value (board_id: 157244624,item_id: 9539475, column_id: "status", value: $value) {
    id
  }
}

query variables:
{
"value": "{\"index\": 1}"
}

Our GraphQL schema defines the structure of the available API data and contains all of the available queries and mutations. It is a valuable resource for verifying API responses and extracting useful information from the metadata.

We expose our schema
here
. By default, it is in introspection JSON format for the
Current
API version. You can request a different version using the optional
version=<API-Version>
parameter with the version name.

For example:
https://api.monday.com/v2/get_schema?version=2024-04

You can also retrieve the schema definition language (SDL) version using the optional
format=sdl
parameter.

For example:
https://api.monday.com/v2/get_schema?format=sdl


### Join our developer community!

We've created a
community
specifically for our devs where you can search through previous topics to find solutions, ask new questions, hear about new features and updates, and learn tips and tricks from other devs. Come join in on the fun! 😎

Updated
7 months ago


---

# Items

Source: https://developer.monday.com/api-reference/docs/items

Updated
about 2 months ago

Updated
about 2 months ago


---

# Items page

Source: https://developer.monday.com/api-reference/docs/items_page

Updated
about 2 months ago

Updated
about 2 months ago


---

# Quick checklist

Source: https://developer.monday.com/api-reference/docs/migrating-user-entity-to-2026-10

Starting with API version
2026-07
, the
User
type and
Query.users
gain new fields, types, enums, and arguments; a new top-level
user_configs
query; and enforced pagination on
users
. Several legacy fields on
User
are deprecated and are scheduled for removal in
2026-10
(confirm availability with introspection or release notes for the version you call).

This guide walks you through migrating an integration from the
2026-04
(or earlier) shape of the
User
entity to the
2026-10
shape.

All prerequisite requests must include the
API-Version: 2026-07
header (or later) to see the new fields, types, and query arguments described below.

Before you migrate, grep your codebase for:

- photo_original
,
photo_thumb
,
photo_thumb_small
,
photo_tiny
,
photo_small
- is_guest
,
is_admin
,
is_view_only
,
is_pending
,
enabled
- is_verified
,
join_date
- encrypt_api_token
,
sign_up_product_kind
- users(kind: ...)
,
users(newest_first: ...)
,
users(non_active: ...)
- users { ... }
calls with
no
limit
argument
(silent pagination cap of 200)
- users(emails: ...)
where any element could be
null
- Reads of
User.birthday
that parse it as a
Date
- Reads of
User.created_at
that parse it as a
Date
(no time component)
- Reads of
User.utc_hours_diff
that assume it's an integer
Each hit has a replacement in the sections below.


## 1. Photo fields →
photo_url
nested object

The five flat photo fields are deprecated. Replace with the nested
PhotoUrl
object.

Before (
2026-04
):


```graphql
query {
  me {
    photo_original
    photo_small
    photo_thumb
    photo_thumb_small
    photo_tiny
  }
}
```

query {
  me {
    photo_original
    photo_small
    photo_thumb
    photo_thumb_small
    photo_tiny
  }
}

After (
2026-07
+):


```graphql
query {
  me {
    photo_url {
      original
      small
      thumb
      thumb_small
      tiny
    }
  }
}
```

query {
  me {
    photo_url {
      original
      small
      thumb
      thumb_small
      tiny
    }
  }
}

photo_url
is nullable (
PhotoUrl
). Each size is also nullable (
String
). Handle the case where the user has no uploaded photo.


## 2. Kind boolean flags →
kind
string

The
is_guest
,
is_admin
, and
is_view_only
booleans are deprecated. Use the
kind
string field instead.

Before:


```graphql
query { users { id is_admin is_guest is_view_only } }
```

query { users { id is_admin is_guest is_view_only } }

After:


```graphql
query { users { id kind } }
```

query { users { id kind } }

Value mapping:


| Before (boolean true) | After (
kind
value) |
| --- | --- |
| is_admin: true | kind == "admin" |
| is_guest: true | kind == "guest" |
| is_view_only: true | kind == "view_only" |

Other
kind
values you may see:
member
,
agent_member
,
portal
, and several
*_api_user
variants (see the full
UserKindFilter
enum).


## 3. Status booleans →
status
enum

is_pending
and
enabled
are replaced by the
status: UserStatus!
field.

Before:


```graphql
query { users { id enabled is_pending } }
```

query { users { id enabled is_pending } }

After:


```graphql
query { users { id status } }
```

query { users { id status } }


| Before | After |
| --- | --- |
| enabled: true
,
is_pending: false | status == ACTIVE |
| enabled: false | status == INACTIVE |
| is_pending: true | status == PENDING |


## 4.
is_verified
→
is_email_confirmed

Same semantics, new name, and the type tightens from
Boolean
to
Boolean!
.

Before:


```graphql
query { me { is_verified } }
```

query { me { is_verified } }

After:


```graphql
query { me { is_email_confirmed } }
```

query { me { is_email_confirmed } }


## 5.
join_date
→
became_active_at

join_date
was a
Date
(
YYYY-MM-DD
).
became_active_at
is an
ISO8601DateTime
with full timestamp precision.

Before:


```graphql
query { me { join_date } }     # "2023-09-02"
```

query { me { join_date } }     # "2023-09-02"

After:


```graphql
query { me { became_active_at } }  # "2023-09-02T13:22:48.000Z"
```

query { me { became_active_at } }  # "2023-09-02T13:22:48.000Z"

If your code parses
join_date
as
YYYY-MM-DD
, slice the first 10 characters of
became_active_at
or parse with a full ISO 8601 parser.


## 6.
Query.users
argument rename:
kind
→
user_kind

Deprecation, not removal.
The legacy
kind
,
newest_first
, and
non_active
arguments (sections 6, 7, and 8) are
deprecated
on
Query.users
starting in
2026-07
and are still deprecated — not removed — in
2026-10
. They continue to work at runtime, so existing queries will not fail schema validation. The schema carries
@deprecated
annotations with replacement reasons, visible via
args(includeDeprecated: true)
or in IDE tooling. A firm removal version has not been announced; migrate off them now so you're ready when one is.

The legacy
kind: UserKind
argument (enum values
all
,
guests
,
non_guests
,
non_pending
) is
deprecated in
2026-07
with
deprecationReason: "Use user_kind instead."
. Replace with
user_kind: UserKindFilterInput
.

Before:


```graphql
query { users(kind: non_guests, limit: 200) { id name } }
```

query { users(kind: non_guests, limit: 200) { id name } }

After:


```graphql
query {
  users(
    user_kind: { not_in: [GUEST] }
    limit: 200
  ) { id name }
}
```

query {
  users(
    user_kind: { not_in: [GUEST] }
    limit: 200
  ) { id name }
}

Migration mapping:


| Legacy
kind
value | New
user_kind |
| --- | --- |
| all | omit the argument |
| guests | { in: [GUEST] } |
| non_guests | { not_in: [GUEST] } |
| non_pending | (no direct equivalent — use
status: [ACTIVE]
instead) |

UserKindFilter
supports both individual kinds (
ADMIN
,
MEMBER
,
GUEST
,
VIEW_ONLY
,
AGENT_MEMBER
,
PORTAL
) and the
BASIC
group (= admin + member + guest + view_only), plus API-user kinds. Use
not_in
to exclude values from an expanded
in
set.


## 7.
Query.users
argument:
newest_first
→
sort

newest_first
is
deprecated in
2026-07
with
deprecationReason: "Use sort instead."
. It still works at runtime.

Before:


```graphql
query { users(newest_first: true, limit: 50) { id created_at } }
```

query { users(newest_first: true, limit: 50) { id created_at } }

After:


```graphql
query {
  users(
    sort: [{ field: CREATED_AT, direction: DESC }]
    limit: 50
  ) { id created_at }
}
```

query {
  users(
    sort: [{ field: CREATED_AT, direction: DESC }]
    limit: 50
  ) { id created_at }
}

sort
takes a list of
UsersSortInput
, so multi-field sorts are supported (
CREATED_AT
is currently the only field).


## 8.
Query.users
argument:
non_active
→
status

non_active
is
deprecated in
2026-07
with
deprecationReason: "Use status instead."
. It still works at runtime.

Before:


```graphql
query { users(non_active: true) { id } }      # all non-active users
query { users(non_active: false) { id } }     # (default) active + pending
```

query { users(non_active: true) { id } }      # all non-active users
query { users(non_active: false) { id } }     # (default) active + pending

After:


```graphql
query { users(status: [INACTIVE]) { id } }
query { users(status: [ACTIVE, PENDING]) { id } }   # (default if omitted)
```

query { users(status: [INACTIVE]) { id } }
query { users(status: [ACTIVE, PENDING]) { id } }   # (default if omitted)

If
status
is omitted, the server defaults to
[ACTIVE, PENDING]
(same as the old
non_active: false
behavior).


## 9. Pagination is now enforced


|  | Before
2026-07 | 2026-07
and later |
| --- | --- | --- |
| users { ... }
(no
limit
) | returned
all
users | returns
200
users |
| users(limit: N)
with
N > 1000 | allowed | error:
Limit exceeds the maximum allowed value of 1000. |

If your code assumed a single call returned the full roster, add explicit pagination:

Before:


```graphql
query { users { id email } }
```

query { users { id email } }

After:


```graphql
query GetAllUsers($page: Int!) {
  users(
    limit: 1000
    page: $page
    sort: [{ field: CREATED_AT, direction: ASC }]
  ) {
    id
    email
  }
}
```

query GetAllUsers($page: Int!) {
  users(
    limit: 1000
    page: $page
    sort: [{ field: CREATED_AT, direction: ASC }]
  ) {
    id
    email
  }
}

Loop over
page = 1, 2, 3, …
until the returned array has fewer than
limit
items.


## 10.
Query.users(emails:)
non-null elements

[String]
→
[String!]
. Ensure you don't pass
null
elements inside the
emails
array — validate input client-side before sending.


## 11.
User
scalar type changes (2026-07)


| Field | 2026-04
type | 2026-07
+ type |
| --- | --- | --- |
| birthday | Date | String |
| created_at | Date | ISO8601DateTime! |
| utc_hours_diff | Int | Float |

- birthday
now ships as a
String
. Treat it as a freeform string; the value is still
YYYY-MM-DD
but the schema no longer guarantees that.
- created_at
now includes a time component (
2023-09-02T13:22:48.000Z
). If you parse with a
Date
-only parser, truncate to 10 characters first.
- utc_hours_diff
is a
Float
. Fractional hours (for example,
5.5
,
-3.5
) can now appear.
You can adopt these at your own pace. They are only available from
2026-07
onward.


## New
User
fields

Safe to add to existing queries once you set the
API-Version: 2026-07
(or later) header.


```graphql
query {
  me {
    id
    account_id              # new
    status                  # new: UserStatus enum
    invitation_method       # new: InvitationMethod enum
    serial_number           # new: Int, nullable
    is_deleted              # new: Boolean!
    became_active_at        # new: ISO8601DateTime
    bb_visitor_id           # new: ID!
    is_email_confirmed      # new: Boolean!
    photo_url { original thumb }
    user_config { kind role_id visibility }
  }
}
```

query {
  me {
    id
    account_id              # new
    status                  # new: UserStatus enum
    invitation_method       # new: InvitationMethod enum
    serial_number           # new: Int, nullable
    is_deleted              # new: Boolean!
    became_active_at        # new: ISO8601DateTime
    bb_visitor_id           # new: ID!
    is_email_confirmed      # new: Boolean!
    photo_url { original thumb }
    user_config { kind role_id visibility }
  }
}


## New
user_configs
query


```graphql
query {
  user_configs {
    kind
    role_id
    visibility
  }
}
```

query {
  user_configs {
    kind
    role_id
    visibility
  }
}

Requires
users:read
and user authorization. Returns every user config for the account, sorted by
role_id
ascending. Optional filters:
kinds: [String]
,
visibility: String
.


| You are on | Minimum target | Do this |
| --- | --- | --- |
| 2025-10
or earlier | 2026-07 | Everything above plus the
2026-04
migration
. |
| 2026-04 | 2026-07 | Apply sections 1–11 when you bump the
API-Version
header. |
| 2026-07 | 2026-10 | No new breaking changes for the user entity itself. Double-check that you've already removed the legacy fields listed in sections 1–5 — they are planned for hard removal in
2026-10
. |

- Set the version header:
API-Version: 2026-07
(or
2026-10
).
- Run your existing queries. The deprecated
kind
,
newest_first
, and
non_active
arguments still work, so queries using them won't fail — but codegen and IDE tooling will surface
@deprecated
warnings once you regenerate against the new schema. Migrate them per sections 6–8.
- Add an explicit
limit
+
page
loop wherever you previously called
users { ... }
with no limit — the silent 200-row cap is the most common surprise in
2026-07
.
- For clients generated from introspection, regenerate against
https://api.monday.com/v2/get_schema?version=2026-07
. If your tooling supports it, pass
includeDeprecated: true
so the deprecated args show up in the dump — the default endpoint omits them.
- Confirm every hit from the
Quick checklist
is addressed before you roll out.
Updated
22 days ago


---

# Monitor your usage

Source: https://developer.monday.com/api-reference/docs/optimizing-api-usage

API
rate limits
are designed to reduce the load on the API and help maintain optimal performance. By following the tips outlined below, you can monitor and optimize your usage to avoid hitting those limits.


## Analytics dashboard

The
API analytics dashboard
monitors your API usage and tracks your account's daily usage, trends, and top contributors.

You can use this data to:

- Detect sudden spikes:
Spikes can be one indicator of a bug in an application. Bugs can cause the app to consume a disproportionate amount of the API budget.
- Evaluate app usage:
Sometimes, apps are no longer used but continue to run and use your API budget. This is often the cause of high API usage in companies with many applications. You can use these insights to evaluate which apps are consuming your API budget and determine whether or not they're still required.
The analytics dashboard is only available for Enterprise accounts.


## platform_api
object

On top of the API analytics dashboard, you can retrieve your account's daily usage, trends, and top contributors by querying the
platform_api
object.


```graphql
query {
  platform_api {
    daily_analytics {
      by_day { 
        day
        usage
      }
      by_app {
        app {
          name
        }
        api_app_id
        usage
      }
      by_user {
        user {
          name
        }
        usage
      }
      last_updated
    }
  }
}
```

query {
  platform_api {
    daily_analytics {
      by_day { 
        day
        usage
      }
      by_app {
        app {
          name
        }
        api_app_id
        usage
      }
      by_user {
        user {
          name
        }
        usage
      }
      last_updated
    }
  }
}


## Maintain logs

Maintaining detailed logs of your API calls allows you to understand the cost of each and track your remaining budget. This data helps with resource allocation and ensuring you don't reach the limits.

Here are some key points to log:

- Complexity cost of the query
- Remaining budget for API calls
- Structure of the query (e.g., the fields requested, filters applied)
- Instances when your app hits the per-minute limit

## Evaluate your use case

Consider evaluating whether the monday.com platform API is the right tool for your use case. Keep in mind that monday.com excels as a work management tool, not as a high-frequency database.


## Implement pagination

Pagination divides your results into smaller sets of data called pages, instead of returning everything at once. You can then utilize cursor-based pagination or the
page
argument to return data from subsequent pages. Doing so helps you avoid consuming a disproportionate amount of your API budget while reducing the load on the API and improving response time.

Example: Instead of returning 10,000 items in your call, use
cursor-based pagination
to return 200 items over 50 calls.

Please note that some queries don't support cursor-based pagination or the
page
argument. Consult our
API reference documentation
to read more about each query and what it supports.


## Use the
change_multiple_column_values
mutation

If you need to modify more than one column value, use
change_multiple_column_values
mutation instead of multiple
change_simple_column_value
mutations. This reduces the number of calls and improves efficiency.


## Simplify your calls

Each call has an associated "cost" that correlates to the load put on the API, also known as the complexity cost. By simplifying your queries, you can reduce their complexity to avoid hitting the
complexity limit
.

- Requesting only the data you need
- Reducing nested queries
- Utilizing the
page
and
limit
arguments
- Filtering your results
You can also calculate the complexity of each query in advance to avoid hitting the limit. The simplest way to do so is by adding the
complexity
field to your queries to return the remaining complexity before and after the query, the complexity of the query itself, and when the limit resets.


```graphql
mutation {
  complexity {
    query
    before
    after
  }
  create_item(board_id:1234567890, item_name: "test item") {
    id
  }
}
```

mutation {
  complexity {
    query
    before
    after
  }
  create_item(board_id:1234567890, item_name: "test item") {
    id
  }
}


## Avoid unnecessary calls

Errors, rate limit responses, and unsuccessful calls all contribute to your daily call limit. You can avoid wasting these calls by retrying your calls only after the required amount of time and properly handling errors.

Example: If you hit the
minute limit
, utilize the
Retry-After
header to determine how long you need to wait before retrying your call.


## Employ fragments

GraphQL is a flexible query language that allows you to only request the information you need in your query. This is done through components like arguments, fields, and
fragments
.

Example: Certain objects, like
column_values
, utilize fragments to return column-specific data, ultimately making your query more efficient.


## Utilize webhooks

If your app needs to respond to changes in monday, use webhooks to receive live alerts. Webhooks are more efficient than periodically polling the API since you will only make API calls as needed.

Please note that webhooks have their own limits (e.g., integration action limits), so it's crucial to strike a balance between webhooks and API usage.


## Implement caching

Consider implementing caching for repeated reads of the same data where live updates aren't critical. This reduces the number of API calls, improves performance, and optimizes your usage.

Updated
7 months ago


---

# Limits

Source: https://developer.monday.com/api-reference/docs/rate-limits

We strive to provide a top-tier API experience that is reliable and consistent for all users. To maintain a high-quality service and ensure optimal performance, users are subject to the following limits to help manage the API's consumption and throughput:

- Complexity limit
- Daily call limit
- Minute limit
- Concurrency limit
- IP limit
- Resource protection limits
Remembering these limits when using the API is crucial to prevent workflow disruptions and delays.


### All limits and exceptions are subject to change. Additional guidelines may be introduced in the future.


## Complexity limit

Complexity defines the load that each call puts on the API. This limit restricts the heaviness of each query to help prevent excessive load and maintain optimal performance. The limit will not affect most users—the quota is set sufficiently high to impact only users making requests that would compromise the stability of the API.

You will receive a
ComplexityException
error if you hit the limit.

The limit varies based on how you're making the call:


| Usage | Limit |
| --- | --- |
| Individual query | 5,000,000 (5M) complexity points |
| Using app tokens to access the API | Read and writes are limited to 5M complexity points per minute* each |
| Using API playground to access the API | Reads and writes are limited to 5M complexity points per minute* each or 1M for trial/free accounts |
| Using personal API tokens to access the API | Reads and writes have a combined budget of 10M points per minute* or 1M for trial, NGO, and free accounts |

*Per-minute budgets follow a sliding window and reset 60 seconds after the first API call was made


### Calculating complexity

Calculating the complexity of each query in advance can prevent you from hitting the limit. The simplest way to do so is by adding the
complexity
field to your queries to return the remaining complexity before and after the query, the complexity of the query itself, and when the limit resets.


```graphql
mutation {
  complexity {
    query
    before
    after
  }
  create_item(board_id:1234567890, item_name:"test item") {
    id
  }
}
```

mutation {
  complexity {
    query
    before
    after
  }
  create_item(board_id:1234567890, item_name:"test item") {
    id
  }
}


### Reducing complexity

You can avoid hitting the complexity limit by:

- Requesting only the data you need
- Reducing nested queries
- Utilizing the
page
and
limit
arguments

## Daily call limit

The daily call limit helps prevent disruptions caused by excessive load from individual accounts, maintains the API service as a free feature across all plans, and controls operational costs to continue delivering value to all our users.

All API calls made through personal tokens, private applications, and public applications (excluding marketplace apps and those developed by monday.com) count towards this limit.

You will receive a
DAILY_LIMIT_EXCEEDED
error if you hit the limit.

The limit varies based on your
monday.com plan
:


| Tier | Daily call limit (resets at midnight UTC) |
| --- | --- |
| Free/Standard/Basic | 1,000 |
| Pro | 10,000 (soft limit)* |
| Enterprise | 25,000 (soft limit)* |

*Indicates the recommended usage. Please request an increase through the
API analytics dashboard
if your account consistently exceeds this limit.


### Exceptions

A single API request typically deducts one call from your daily limit. However, there are exceptions for specific calls:


| API call | Contribution to the daily limit | Resolution |
| --- | --- | --- |
| Requests that hit a rate limit (
complexity
,
minute rate limit
,
concurrency
, etc.) | 0.1 calls | Every rate limit error returns a
retry_in_seconds
field. Only retry your call after waiting for the indicated time to avoid wasteful retries. |
| Querying
complexity
to check a query's complexity cost | 0.1 calls | On their own,
complexity
queries count as
less than one call
. We recommend including this query in other API requests to save this usage. |
| High complexity queries | 1+ calls | Each API call incurs a complexity cost, and some of these calls contribute extra to the daily call limit. To reduce your daily API call usage, you can
reduce your call's complexity
. |


## Minute limit

The minute limit restricts the number of requests in a given period. It is defined per minute, but you may not need to wait for the full minute before retrying your request. You can use the
Retry-After
header to determine when you can retry the request.

You will receive a
Minute limit rate exceeded
error if you hit the limit.

The limit varies based on your
monday.com plan
:


| Tier | Queries per minute |
| --- | --- |
| Enterprise | 5,000 |
| Pro | 2,500 |
| Other | 1,000 |


### Endpoint-specific minute limits

Each endpoint is subject to the limits mentioned above, but some have additional limits to keep in mind:


| Endpoint | Limit |
| --- | --- |
| Create a board mutation | 40 mutations per minute |
| Duplicate a board mutation | 40 mutations per minute |
| Duplicate a group mutation | 40 mutations per minute |
| Connect project to portfolio mutation | 15 mutations per minute |
| Items query | 100 items |
| App subscriptions query | 120 times per minute |
| display_value
field on
FormulaValue
implementation | 10,000 formula values per minute (each cell counts as one)
Up to five formula columns in each request |

Endpoint

Limit

Create a board mutation

40 mutations per minute

Duplicate a board mutation

40 mutations per minute

Duplicate a group mutation

40 mutations per minute

Connect project to portfolio mutation

15 mutations per minute

Items query

100 items

App subscriptions query

120 times per minute

display_value

field on

FormulaValue

implementation

- 10,000 formula values per minute (each cell counts as one)
- Up to five formula columns in each request

## Concurrency limit

The concurrency limit restricts the number of requests being handled at any moment. You will receive a
Concurrency limit exceeded
error if you hit the limit.

The limit varies based on your
monday.com plan
and the type of request:


| Tier | Maximum concurrent requests |
| --- | --- |
| Enterprise | 250 |
| Pro | 100 |
| Other | 40 |


## IP limit

The IP limit helps control the API traffic coming from a given IP address within a short period. You will receive an
IP_RATE_LIMIT_EXCEEDED
error if you hit the limit.


| Source | Limit |
| --- | --- |
| Individual IP address | 5,000 requests per 10 seconds |


## Resource protection limit

In rare cases, an internal monday resource might reject the request. In such a case the same retry logic applies.

- All requests count towards the stated limits,
even those that fail or return an error.
You can prevent unnecessary API usage by waiting for the time indicated in the
retry_in_seconds
field before retrying the call.
- The
API SDK
respects the rate-limited responses and waits the appropriate amount of time before automatically retrying the request, up to a configurable maximum number of retries.
- Unless otherwise noted, limits are measured per account, per app. Usage through a personal token counts toward the same limit.
Updated
6 days ago


---

# Actively supported versions

Source: https://developer.monday.com/api-reference/docs/release-notes

This document lists the actively supported API versions in reverse chronological order, allowing you to quickly view the latest features, fixes, and changes.

Versions earlier than
2025-04
are deprecated and no longer supported, but we’ve kept them in a
Deprecated versions
section at the bottom for migration and troubleshooting reference.


## 2026-10


### Breaking changes

- The User entity migration that started in
2026-07
completes in
2026-10
. See the
User entity migration guide
.
The following legacy
User
fields are removed:
photo_original
,
photo_thumb
,
photo_thumb_small
,
photo_tiny
,
photo_small
,
is_guest
,
is_admin
,
is_view_only
,
is_pending
,
enabled
,
is_verified
,
join_date
,
encrypt_api_token
, and
sign_up_product_kind
The
kind
,
newest_first
, and
non_active
arguments on
Query.users
are removed. Use
user_kind
,
sort
, and
status
instead
- The following legacy
User
fields are removed:
photo_original
,
photo_thumb
,
photo_thumb_small
,
photo_tiny
,
photo_small
,
is_guest
,
is_admin
,
is_view_only
,
is_pending
,
enabled
,
is_verified
,
join_date
,
encrypt_api_token
, and
sign_up_product_kind
- The
kind
,
newest_first
, and
non_active
arguments on
Query.users
are removed. Use
user_kind
,
sort
, and
status
instead

## 2026-07


### Breaking changes

These changes typically cause
GraphQL validation or execution errors
when an integration has not been updated (wrong arguments, invalid input, or over-limit).

- The
User
type and
Query.users
are overhauled in
2026-07
with new fields, types, enums, query arguments, and enforced pagination. See the
User entity migration guide
for full details and code examples.
Query.users
emails
argument: element type is now non-null (
[String!]
). Requests that include
null
inside the
emails
array fail validation
Query.users
limit
: values above
1000
are rejected with an error (maximum
limit
is 1000)
- Query.users
emails
argument: element type is now non-null (
[String!]
). Requests that include
null
inside the
emails
array fail validation
- Query.users
limit
: values above
1000
are rejected with an error (maximum
limit
is 1000)

### Non-breaking changes

- New
create_validation_rule
,
update_validation_rule
, and
delete_validation_rule
mutations for board validation rules (see
Validation rules guide
)
- New
create_doc_blocks
mutation with structured
CreateBlockInput
for rich document blocks (see
Document blocks V2
)
- New
inferred_metadata
and
manual_metadata
fields on the
Board
type
- The
User
type and
Query.users
gain new fields, types, enums, input types, and arguments. Several legacy fields and arguments are deprecated (scheduled for removal in
2026-10
), and a few scalar types change behavior silently. See the
User entity migration guide
for full details and code examples.
New
activity_logs
field on the
User
type for querying user-scoped activity log events with cursor-based pagination
New fields on the
User
type:
account_id
,
status
,
invitation_method
,
serial_number
,
is_deleted
,
photo_url
,
became_active_at
,
bb_visitor_id
,
is_email_confirmed
, and
user_config
New
user_configs
query to retrieve per-kind user configuration for the account
New
PhotoUrl
and
UserConfig
types on
User
New
UserStatus
,
InvitationMethod
,
UserKindFilter
,
UsersSortField
, and
UsersSortDirection
enums
New
UserKindFilterInput
and
UsersSortInput
input types
New
user_kind
,
sort
,
status
, and
visibility
arguments on
Query.users
The
kind
,
newest_first
, and
non_active
arguments on
Query.users
are deprecated and scheduled for removal in
2026-10
. Use
user_kind
,
sort
, and
status
instead
The following
User
fields are deprecated and scheduled for removal in
2026-10
:
photo_original
,
photo_thumb
,
photo_thumb_small
,
photo_tiny
,
photo_small
,
is_guest
,
is_admin
,
is_view_only
,
is_pending
,
enabled
,
is_verified
,
join_date
,
encrypt_api_token
, and
sign_up_product_kind
Dangerous change:
Query.users
without
limit
now returns only
200
users by default (previously unbounded). Jobs that relied on one call returning the full account roster will silently under-fetch — use explicit
limit
and
page
Dangerous change:
User.created_at
scalar type changed from
Date
to
ISO8601DateTime!
(includes a time component; non-null in the schema). Clients that treat the value as date-only may mis-parse or drop information
Dangerous change:
User.birthday
type changed from
Date
to
String
(no longer a dedicated
Date
scalar)
Dangerous change:
User.utc_hours_diff
type changed from
Int
to
Float
(fractional hour offsets are possible). Logic that assumes an integer may produce incorrect results even though the query succeeds
- New
activity_logs
field on the
User
type for querying user-scoped activity log events with cursor-based pagination
- New fields on the
User
type:
account_id
,
status
,
invitation_method
,
serial_number
,
is_deleted
,
photo_url
,
became_active_at
,
bb_visitor_id
,
is_email_confirmed
, and
user_config
- New
user_configs
query to retrieve per-kind user configuration for the account
- New
PhotoUrl
and
UserConfig
types on
User
- New
UserStatus
,
InvitationMethod
,
UserKindFilter
,
UsersSortField
, and
UsersSortDirection
enums
- New
UserKindFilterInput
and
UsersSortInput
input types
- New
user_kind
,
sort
,
status
, and
visibility
arguments on
Query.users
- The
kind
,
newest_first
, and
non_active
arguments on
Query.users
are deprecated and scheduled for removal in
2026-10
. Use
user_kind
,
sort
, and
status
instead
- The following
User
fields are deprecated and scheduled for removal in
2026-10
:
photo_original
,
photo_thumb
,
photo_thumb_small
,
photo_tiny
,
photo_small
,
is_guest
,
is_admin
,
is_view_only
,
is_pending
,
enabled
,
is_verified
,
join_date
,
encrypt_api_token
, and
sign_up_product_kind
- Dangerous change:
Query.users
without
limit
now returns only
200
users by default (previously unbounded). Jobs that relied on one call returning the full account roster will silently under-fetch — use explicit
limit
and
page
- Dangerous change:
User.created_at
scalar type changed from
Date
to
ISO8601DateTime!
(includes a time component; non-null in the schema). Clients that treat the value as date-only may mis-parse or drop information
- Dangerous change:
User.birthday
type changed from
Date
to
String
(no longer a dedicated
Date
scalar)
- Dangerous change:
User.utc_hours_diff
type changed from
Int
to
Float
(fractional hour offsets are possible). Logic that assumes an integer may produce incorrect results even though the query succeeds

## 2026-04


### Breaking changes

- The
value_string
,
value_int
,
value_float
, and
value_boolean
fields on
AggregateGroupByResult
have been
replaced by a unified
value
field of type
JSON

### Non-breaking changes

- New
create_project
mutation
- New
set_item_description_content
mutation
- New
create_marketplace_app_discount
mutation
- New
feature-level lifecycle event subscriptions
APIs
- New APIs to
manage departments
- New ability to
update an item's nickname
- New
search
query
for cross-entity search across items, boards, and documents
- New
articles
query and mutations
for Knowledge Base article CRUD and publishing
- New
article_blocks
query
for paginated article content blocks
- New
knowledge_base_search
query
for AI-powered knowledge base search
- New
doc_version_history
query
to retrieve document version snapshots
- New
doc_version_diff
query
to compare document versions
- New
notetaker
query namespace
for meeting recordings, transcripts, summaries, and action items
- New
object_relations
query and mutations
for managing relations (aliases and dependencies) between objects
- New
relations
argument
on
create_object
mutation
- New
relations
field
on
Object
type
- New
allowed_sequences_to_enroll
query and
enroll_items_to_sequence
mutation for
email sequences
- New
tool_events
query
for MCP tool execution events in automations
- New
ask_developer_docs
query
for AI-powered developer documentation answers
- New
prompt
argument
on
create_board
mutation to generate board structure via AI
- New
query_params
argument
on
workspaces
query to filter by account product kind
- New
created_from_board_id
and
folder
fields
on
Board
type
- New
department
field
on
User
type
- New
attribution_entity_ref
and
attribution_entity_type
fields
on
Like
type for reaction attribution
- New
app_feature_slug
field
on
Folder
type
- New
APP_FEATURE
and
LISTVIEW
values
on
ExternalWidget
enum

## 2026-01


### Non-breaking changes

- New
aggregate
object
- New
max_units
field
- New
updated_at
field
- New
width
argument on
update_column
mutation
- New
created_at
field on
account
- New
membership_kind
argument on
workspaces
- New
is_trial_expired
and
is_during_trial
fields on
account
- New
mutations
to create status and dropdown columns attached to managed columns
- New
Resource Directory APIs
- New
tier
field available on account
products
queries

## 2025-10


### Breaking changes

- Updated
complexity error format

### Non-breaking changes

- New
update_doc_name
mutation
- New
duplicate_doc
mutation
- New
delete_doc
mutation
- New
change_item_position
mutation
- New ability to
change a workspace's account product
- New
set_board_permissions
mutation
- New
update_board_hierarchy
mutation
- New
update_folder
mutation arguments
- New
views
fields
- New
replies
arguments
- New
create_update
arguments
- Filter for
board level updates
in the
updates
field
- New
create_portfolio
mutation
- New ability to read
Workforms
- New
connect_project_to_portfolio
mutation
- New ability to
create, update, and delete Workforms
- New mutations to
create, update, and delete dashboards
- New
mute_board_settings
object
- New
CRUD capabilities
for managing favorites
- New
create_widget
mutation
- New
convert_board_to_project
mutation
- Improved
API complexity calculation
- New mutations to
create, update, and delete board views
- New
add_content_to_doc_from_markdown
mutation
- New
import_doc_from_html
mutation
- New
get_column_type_schema
object
- New ability to
create mirror and connect board columns
- New
update_mute_board_settings
mutation
- New
notifications_settings
object
- New ability to
create, read, update, and delete monday.com objects
- New mutations to
create and update app features
- New ability to
create, read, and delete required field columns
- New
columns
fields
- New API support for
multi-level boards
- New
update_column
mutation
- New
delete_widget
mutation
- New
app
fields
- New mutations to
create and update apps
- New mutations to
create status and dropdown columns
- New
item_nickname
argument on
create_board
mutation
- New mutations to
update dropdown and status columns
- New
export_markdown_from_doc
object
- Deprecating
settings_str
field on
columns

## 2025-07


### Hotfixes

- April 28th, 2025:
For column value exception errors, the
column_type
property no longer returns "Column" appended to the column type. Read more
here
.
- May 19th, 2025:
All API responses now contain a unique request ID. Read more
here
.

### Breaking changes

- Updated
complexity budget exhausted error
- Updated
unauthorized user error code

### Non-breaking changes

- New argument to create
empty boards
- New argument to specify product for
workspace creation
- New
field
to retrieve assets on
Reply
object
- New
item description
field
- New
CRUD capabilities
for managed columns
- New
mentions_list
argument in
create_update
mutations
- New
arguments
to filter
updates
by date
- New
fields
for
boards
queries
- New
access_level
field for board view queries
- New ability to read
audit logs
via the API
- New
audit_event_catalogue
object to retrieve a list of supported audit log events

## 2025-04


### Hotfixes

- February 18th, 2025
: The complexity budget exhausted error format has changed. Read more
here
.
- February 24th, 2025
: The
create_webhook
mutation now returns descriptive errors. Read more
here
.
- February 24th, 2025
: The
renewal_date
field is no longer required when querying app subscription details. Read more
here
.
- February 27th, 2025:
We've introduced changes to the
subitems
query to help increase performance and return consistent results. Read more
here
.
- April 28th, 2025:
For column value exception errors, the
column_type
property no longer returns "Column" appended to the column type. Read more
here
.
- May 19th, 2025:
All API responses now contain a unique request ID. Read more
here
.

### Breaking changes

- Deprecated: Sending variables as a
JSON string
- Value field now
returns null
on connect boards, dependency, and subtasks columns

### Non-breaking changes

- New
page_break
type on
create_doc_block
mutation
- New
invite_users
mutation
- New
end_date
field on app subscription details object
- New
update user attributes
mutation
- New
max_units
field on app subscription queries
- New
max_units
argument on set mock app subscription mutations
- New ability to query user profile
custom fields
- New
account_roles
object
- New ability to
update a user's custom role
- New
platform_api
object to query daily API usage
- New
object
to query app data
This section covers API versions that are deprecated and no longer supported. They are documented here for historical and migration reference only. Review our API versioning policy for upcoming deprecation timelines.


## 2025-01


### Hotfixes

- February 18th, 2025
: The complexity budget exhausted error format has changed. Read more
here
.
- February 24th, 2025
: The
create_webhook
mutation now returns descriptive errors. Read more
here
.
- February 24th, 2025
: The
renewal_date
field is no longer required when querying app subscription details. Read more
here
.
- February 27th, 2025:
We've introduced changes to the
subitems
query to help increase performance and return consistent results. Read more
here
.
- April 28th, 2025:
For column value exception errors, the
column_type
property no longer returns "Column" appended to the column type. Read more
here
.
- May 19th, 2025:
All API responses now contain a unique request ID. Read more
here
.

### Breaking changes

- New
unified error responses
that comply with the GraphQL standard
- More spec-compliant
GraphQL query validation
- Column validation
for apps
- Account ID
no longer returned by default
- New
pagination limit
for
updates
queries
- GraphQL queries now
required in request body

### Non-breaking changes

- New
create and delete team
mutations
- New
app_subscriptions
object
- New
updates
fields
- New ability to
read the formula column
- New
deactivate_users
mutation
- New
update_users_role
mutation
- New
assign_team_owners
mutation
- New
remove_team_owners
mutation
- New
update_email_domain
mutation
- New
timeline
object
- New
activate_users
mutation
- New
timeline_item
fields

## 2024-10


### Hotfixes

- October 22nd, 2024
: The
item_id
argument on the
pin_to_top
and
unpin_from_top
mutations has changed from type
Int
to
ID
and is no longer required. Read more
here
.
- November 6th, 2024
: We made version
2024-10
backward compatible to resolve parsing errors. Read more
here
.
- November 19th, 2024
: Updates should be returned in reverse chronological order instead of chronological order. Read more
here
.
- February 24th, 2025
: The
create_webhook
mutation now returns descriptive errors. Read more
here
.
- February 27th, 2025:
We've introduced changes to the
subitems
query to help increase performance and return consistent results. Read more
here
.
- April 28th, 2025:
For column value exception errors, the
column_type
property no longer returns "Column" appended to the column type. Read more
here
.
- May 19th, 2025:
All API responses now contain a unique request ID. Read more
here
.

### Non-breaking changes

- New
marketplace_app_discounts
object
- New
grant_marketplace_app_discounts
and
delete_marketplace_app_discounts
mutations
- New
errors
object in API errors
- New descriptive
field limit exceeded
error
- New descriptive
JSON parse
error
- New Emails & Activities
timeline_items
object
- New Emails & Activities
custom_activity
object
- New
updates
object queries and mutations
- New
team_owners
and
team_subscribers
fields on
boards
queries

## 2024-07


### Hotfixes

- April 1st, 2024
: You can now filter the date column with multiple exact dates. Check out the full announcement
here
.
- May 1st, 2024
: Changes to the
ComplexityException
error structure and error code were reverted. Read more
here
.
- May 9th, 2024
: The addition of the
data
object to error codes has been rolled back until version
2025-01
. Read more
here
.
- May 14th, 2024
: Changes to the
ComplexityException
error message were reverted. Read more
here
.
- June 19th, 2024
: New descriptive JSON parse error added to all API versions. Read more
here
.
- June 20th, 2024
: You can now use the
add_teams_to_board
mutation to subscribe everyone in an account to a board. Check out the full announcement
here
.

### Non-breaking changes

- New
active_members_count
field on
account
queries
- New
apps_monetization_info
object

## 2024-04


### Hotfixes

- March 26th, 2024
: Mutations with the
column_values
argument now accept both string and integer IDs. Check out the full announcement
here
.
- April 1st, 2024
: You can now filter the date column with multiple exact dates. Check out the full announcement
here
.
- May 1st, 2024
: Changes to the
ComplexityException
error structure, error code, and error message were reverted. Read more
here
.
- May 14th, 2024
: Changes to the
ComplexityException
error message were reverted. Read more
here
.
- June 19th, 2024
: New descriptive JSON parse error added to all API versions. Read more
here
.
- June 20th, 2024
: You can now use the
add_teams_to_board
mutation to subscribe everyone in an account to a board. Check out the full announcement
here
.

### Breaking changes

- New
kind
field accepted enum values on
version
and
versions
queries
- Updated
field types
on
app_installs
queries

### Non-breaking changes

- New
voters
field on
VoteValue
- New
url
field on
boards
and
items
queries
- New
group_color
argument for
create_group
mutation
- New
display_value
field on
version
and
versions
queries
- New
account_id
argument and
permissions
field
on
app_installs
queries
- New
position_relative_method
and
relative_to
arguments
on
create_item
mutation
- New
is_default_workspace
field on
workspaces
queries
- New
date column filtering
with multiple exact dates
- Create a doc column
using the
create_column
mutation
- New
app_subscription_operations
queries and mutations

## 2024-01


### Hotfixes

- March 26th, 2024
: Mutations with the
column_values
argument now accept both string and integer IDs. Check out the full announcement
here
.
- May 1st, 2024
: Changes to the
ComplexityException
error structure, error code, and error message were reverted. Read more
here
.
- May 14th, 2024
: Changes to the
ComplexityException
error message were reverted. Read more
here
.
- June 19th, 2024
: New descriptive JSON parse error added to all API versions. Read more
here
.
- June 20th, 2024
: You can now use the
add_teams_to_board
mutation to subscribe everyone in an account to a board. Check out the full announcement
here
.

### Breaking changes

- Typo fix in the
UserUnauthorizedException
error code
- New
DeleteLastGroupException
error

### Non-breaking changes

- New
app_installs
object to retrieve app installation data
- New
pricing_version
field on app subscription queries
- New
team_owners_subscribers
field on workspaces queries
- New
delete_teams_from_board
mutation
- New
kind
argument on
add_teams_to_board
- New
add_users_to_team
and
remove_users_from_team
mutations
- New
update_workspace
mutation

## 2023-10


### Hotfixes

- December 3rd, 2023:
We aligned the empty value results for the
text
field when querying through
column_values
V2 to the behavior seen in version
2023-07
.  Check out the full announcement
here
.
- March 26th, 2024
: Mutations with the
column_values
argument now accept both string and integer IDs. Check out the full announcement
here
.
- June 19th, 2024
: New descriptive JSON parse error added to all API versions. Read more
here
.
- June 20th, 2024
: You can now use the
add_teams_to_board
mutation to subscribe everyone in an account to a board. Check out the full announcement
here
.

### Breaking changes

- Removed the deprecated
items
field on
boards
queries, replaced it with
items_page
Removed the deprecated
items
field on
boards
queries, replaced it with
items_page

- Removed the deprecated
items
field on
groups
queries, replaced it with
items_page
Removed the deprecated
items
field on
groups
queries, replaced it with
items_page

- New
column values
fields and typed column values
New
column values
fields and typed column values

- Removed the deprecated
items_by_column_values
and
items_by_multiple_column_values
objects, replaced them with
items_page_by_column_values
Removed the deprecated
items_by_column_values
and
items_by_multiple_column_values
objects, replaced them with
items_page_by_column_values

- The
column_type
field on the
create_column
mutation is now required
The
column_type
field on the
create_column
mutation is now required

- Empty parentheses are
no longer supported
Empty parentheses are
no longer supported

- Quotation marks for strings are
now required
Quotation marks for strings are
now required

- Removed the deprecated
pos
fields on boards and columns queries
Removed the deprecated
pos
fields on boards and columns queries

- Column type strings have changed. The
type
field
on
columns
queries has changed from
String!
to
ColumnType!
Column type strings have changed. The
type
field
on
columns
queries has changed from
String!
to
ColumnType!

- Deprecated the
newest_first
argument on
boards
queries
Deprecated the
newest_first
argument on
boards
queries

- Many of the
ID arguments and fields
have changed from
Int
to
ID
type
Many of the
ID arguments and fields
have changed from
Int
to
ID
type

- Text
field returns
empty results
for mirror, dependency, and connect boards columns when querying through
column_values
or the specific
MirrorValue
,
DependencyValue
and
BoardRelationValue
types. Use the
display_value
field instead.
Text
field returns
empty results
for mirror, dependency, and connect boards columns when querying through
column_values
or the specific
MirrorValue
,
DependencyValue
and
BoardRelationValue
types. Use the
display_value
field instead.


### Non-breaking changes

- New
next_items_page
object for cursor-based pagination
New
next_items_page
object for cursor-based pagination

- New
move_item_to_board
mutation
New
move_item_to_board
mutation

- New
linked_items
field on
items
queries
New
linked_items
field on
items
queries

- New
edit_update
and
delete_update
webhooks
New
edit_update
and
delete_update
webhooks

- The
value
argument in the
change_simple_column_value
mutation is now nullable
The
value
argument in the
change_simple_column_value
mutation is now nullable

- The complexity of the
text
field for mirror, link, and dependency columns increased
The complexity of the
text
field for mirror, link, and dependency columns increased

- New
ids
argument on
updates
queries
New
ids
argument on
updates
queries

Updated
11 days ago


---

# Access the Developer Center

Source: https://developer.monday.com/api-reference/docs/the-developer-center

The Developer Center is a one-stop-shop to manage your
monday apps
and API usage. For API users, you can access the API playground, view your API token, and monitor your API usage through the API analytics dashboard.

- Open your monday.com account or
sign up
for a free developer account!
- Click your profile picture in the top right corner.
- Select
Developers
.
- This will open the Developer Center in a new tab.
- From there, you can navigate to the tabs in the left-side menu to manage your API usage.

## API playground

The
API playground
tab quickly connects you to our authenticated testing space where you can practice API calls, view the schema, and read the documentation. Check out this
video
to learn more about the playground!


## API token

You can view or regenerate your API
access token
in the
API token
tab.


## API analytics

The
API analytics
tab opens your
API analytics dashboard
where you can track your account's daily API usage, trends, and top contributors.

Updated
7 months ago


---

# Key concepts

Source: https://developer.monday.com/api-reference/docs/validation-rules-guide

Only available in API versions
2026-07
and later

Validation rules let you enforce data quality on monday.com boards by defining constraints on column values. Unlike
required columns
which simply mark a column as mandatory, validation rules support comparison operators, value ranges, and conditional logic. For an overview of the feature in the monday.com UI, see
Data validations
.

This guide walks you through the validation rules API from basic constraints to conditional rules. By the end, you'll be able to programmatically enforce business rules like "amounts must be at least 5" or "if the status is Done, the description must be filled in."


## How validation rules work

A validation rule has two parts:


| Part | Required | Description |
| --- | --- | --- |
| then | Yes | The constraint that must be satisfied. Defines what the column value should look like. |
| if | No | A condition that triggers the rule. When provided, the
then
constraint only applies when the
if
condition is met. |

Rules without an
if
clause are
validation rules
— they always apply. Rules with an
if
clause are
conditional rules
— they only apply when the condition is met.


## Enforcement

Validation rules are enforced both in the
monday.com interface
and through the
API
. When you create or update items via mutations like
create_item
,
change_simple_column_value
, or
change_column_values
, the API checks active validation rules and rejects requests that violate them with a
DATA_VALIDATIONS_ERROR
error (422 status code).

The error response includes details about which columns failed validation:


```graphql
{
  "errors": [
    {
      "message": "data_validation_error",
      "extensions": {
        "code": "DATA_VALIDATIONS_ERROR",
        "status_code": 422,
        "error_data": [
          {
            "itemId": null,
            "columnIds": ["numeric_mm1pddwd"],
            "message": "'Amount' must be at least [5]"
          }
        ]
      }
    }
  ]
}
```

{
  "errors": [
    {
      "message": "data_validation_error",
      "extensions": {
        "code": "DATA_VALIDATIONS_ERROR",
        "status_code": 422,
        "error_data": [
          {
            "itemId": null,
            "columnIds": ["numeric_mm1pddwd"],
            "message": "'Amount' must be at least [5]"
          }
        ]
      }
    }
  ]
}


## Relationship to required columns

Validation rules and required columns are separate features that coexist on the same board:

- Required columns
(
add_required_column
/
remove_required_column
) mark a column as mandatory. The column must have a value, but there's no constraint on
what
that value is.
- Validation rules
(
create_validation_rule
/
update_validation_rule
/
delete_validation_rule
) define constraints on
what
values are acceptable.
Both appear in the
validations
query response — required columns in
required_column_ids
and rules in
rules
.

- API authentication token
- A board ID (find it in the URL:
monday.com/boards/{board_id}
)
- Familiarity with the column IDs on your board (query
boards
→
columns
→
id
)
- Requests must include the
API-Version: 2026-07
header
- Pro or Enterprise
monday.com account

## Validation rule

Let's create a rule that requires a status column to be one of two specific values (label indices
1
and
2
):


```graphql
mutation {
  create_validation_rule(
    id: 1234567890,
    type: board,
    rule: {
      then: {
        operator: AND,
        groups: [{
          operator: ANY_OF,
          column_id: "status",
          compare_value: [1, 2]
        }]
      }
    }
  ) {
    id
    if
    then
  }
}
```

mutation {
  create_validation_rule(
    id: 1234567890,
    type: board,
    rule: {
      then: {
        operator: AND,
        groups: [{
          operator: ANY_OF,
          column_id: "status",
          compare_value: [1, 2]
        }]
      }
    }
  ) {
    id
    if
    then
  }
}

The response includes the generated rule ID:


```graphql
{
  "data": {
    "create_validation_rule": {
      "id": "cd7f1b7b-452e-40d3-886c-346184ffee7e",
      "if": null,
      "then": {
        "operator": "AND",
        "groups": [
          {
            "operator": "ANY_OF",
            "column_id": "status",
            "compare_value": [1, 2]
          }
        ]
      }
    }
  }
}
```

{
  "data": {
    "create_validation_rule": {
      "id": "cd7f1b7b-452e-40d3-886c-346184ffee7e",
      "if": null,
      "then": {
        "operator": "AND",
        "groups": [
          {
            "operator": "ANY_OF",
            "column_id": "status",
            "compare_value": [1, 2]
          }
        ]
      }
    }
  }
}

Key things to note:

- The
then
clause requires an
operator
(
AND
or
OR
) and a
groups
array of constraints
- Each constraint targets a
column_id
with a comparison
operator
and optional
compare_value
- Validation rules (without an
if
clause) return
null
for the
if
field
- The returned
id
is a UUID you'll use for updates and deletes

## Numeric constraint

Require a numbers column to be at least 5:


```graphql
mutation {
  create_validation_rule(
    id: 1234567890,
    type: board,
    rule: {
      then: {
        operator: AND,
        groups: [{
          operator: GREATER_THAN_OR_EQUALS,
          column_id: "numbers0",
          compare_value: [5]
        }]
      }
    }
  ) {
    id
    then
  }
}
```

mutation {
  create_validation_rule(
    id: 1234567890,
    type: board,
    rule: {
      then: {
        operator: AND,
        groups: [{
          operator: GREATER_THAN_OR_EQUALS,
          column_id: "numbers0",
          compare_value: [5]
        }]
      }
    }
  ) {
    id
    then
  }
}


## Date range constraint

Require a date column to fall within a specific range:


```graphql
mutation {
  create_validation_rule(
    id: 1234567890,
    type: board,
    rule: {
      then: {
        operator: AND,
        groups: [{
          operator: BETWEEN,
          column_id: "date0",
          compare_value: ["2026-01-01", "2026-12-31"]
        }]
      }
    }
  ) {
    id
    then
  }
}
```

mutation {
  create_validation_rule(
    id: 1234567890,
    type: board,
    rule: {
      then: {
        operator: AND,
        groups: [{
          operator: BETWEEN,
          column_id: "date0",
          compare_value: ["2026-01-01", "2026-12-31"]
        }]
      }
    }
  ) {
    id
    then
  }
}


## Text constraint

Require a text column to contain a specific substring:


```graphql
mutation {
  create_validation_rule(
    id: 1234567890,
    type: board,
    rule: {
      then: {
        operator: AND,
        groups: [{
          operator: CONTAINS_TEXT,
          column_id: "text0",
          compare_value: ["REQ-"]
        }]
      }
    }
  ) {
    id
    then
  }
}
```

mutation {
  create_validation_rule(
    id: 1234567890,
    type: board,
    rule: {
      then: {
        operator: AND,
        groups: [{
          operator: CONTAINS_TEXT,
          column_id: "text0",
          compare_value: ["REQ-"]
        }]
      }
    }
  ) {
    id
    then
  }
}

Conditional rules use an
if
clause to gate when the
then
constraint applies. This lets you build logic like "if the status is Done, then the description must be filled in."


## Basic conditional rule


```graphql
mutation {
  create_validation_rule(
    id: 1234567890,
    type: board,
    rule: {
      if: {
        operator: AND,
        groups: [{
          operator: ANY_OF,
          column_id: "status",
          compare_value: [1]
        }]
      },
      then: {
        operator: AND,
        groups: [{
          operator: IS_NOT_EMPTY,
          column_id: "text0"
        }]
      }
    }
  ) {
    id
    if
    then
  }
}
```

mutation {
  create_validation_rule(
    id: 1234567890,
    type: board,
    rule: {
      if: {
        operator: AND,
        groups: [{
          operator: ANY_OF,
          column_id: "status",
          compare_value: [1]
        }]
      },
      then: {
        operator: AND,
        groups: [{
          operator: IS_NOT_EMPTY,
          column_id: "text0"
        }]
      }
    }
  ) {
    id
    if
    then
  }
}


### IS_NOT_EMPTY in conditional rules

The
IS_NOT_EMPTY
operator is only available inside conditional rules (rules with an
if
clause). It cannot be used in standalone validation rules. You can use it in both the
if
and
then
clauses — for example, to trigger a rule when one column is not empty, or to require a column to have a value when a condition is met.


## Multiple then constraints

Conditional rules can enforce multiple constraints at once. If a condition is met, require both a numbers column and a date column to be filled:


```graphql
mutation {
  create_validation_rule(
    id: 1234567890,
    type: board,
    rule: {
      if: {
        operator: AND,
        groups: [{
          operator: ANY_OF,
          column_id: "priority",
          compare_value: [1]
        }]
      },
      then: {
        operator: AND,
        groups: [
          {
            operator: IS_NOT_EMPTY,
            column_id: "numbers0"
          },
          {
            operator: IS_NOT_EMPTY,
            column_id: "date0"
          }
        ]
      }
    }
  ) {
    id
    if
    then
  }
}
```

mutation {
  create_validation_rule(
    id: 1234567890,
    type: board,
    rule: {
      if: {
        operator: AND,
        groups: [{
          operator: ANY_OF,
          column_id: "priority",
          compare_value: [1]
        }]
      },
      then: {
        operator: AND,
        groups: [
          {
            operator: IS_NOT_EMPTY,
            column_id: "numbers0"
          },
          {
            operator: IS_NOT_EMPTY,
            column_id: "date0"
          }
        ]
      }
    }
  ) {
    id
    if
    then
  }
}


## Update a rule

Use
update_validation_rule
with the rule's ID. You must provide the full rule definition — partial updates are not supported:


```graphql
mutation {
  update_validation_rule(
    id: 1234567890,
    type: board,
    rule_id: "cd7f1b7b-452e-40d3-886c-346184ffee7e",
    rule: {
      then: {
        operator: AND,
        groups: [{
          operator: GREATER_THAN_OR_EQUALS,
          column_id: "numbers0",
          compare_value: [10]
        }]
      }
    }
  ) {
    id
    if
    then
  }
}
```

mutation {
  update_validation_rule(
    id: 1234567890,
    type: board,
    rule_id: "cd7f1b7b-452e-40d3-886c-346184ffee7e",
    rule: {
      then: {
        operator: AND,
        groups: [{
          operator: GREATER_THAN_OR_EQUALS,
          column_id: "numbers0",
          compare_value: [10]
        }]
      }
    }
  ) {
    id
    if
    then
  }
}


## Delete a rule


```graphql
mutation {
  delete_validation_rule(
    id: 1234567890,
    type: board,
    rule_id: "cd7f1b7b-452e-40d3-886c-346184ffee7e"
  ) {
    id
  }
}
```

mutation {
  delete_validation_rule(
    id: 1234567890,
    type: board,
    rule_id: "cd7f1b7b-452e-40d3-886c-346184ffee7e"
  ) {
    id
  }
}

The mutation returns the deleted rule's data.

Query the
validations
endpoint to see all validation rules and required columns on a board:


```graphql
query {
  validations(id: 1234567890) {
    required_column_ids
    rules
  }
}
```

query {
  validations(id: 1234567890) {
    required_column_ids
    rules
  }
}

The
rules
field returns a JSON object where each key is a rule ID and each value is the rule definition:


```graphql
{
  "data": {
    "validations": {
      "required_column_ids": null,
      "rules": {
        "80d2c9d3-c93d-40be-9d34-b611241345b5": {
          "then": {
            "operator": "AND",
            "groups": [{
              "operator": "GREATER_THAN_OR_EQUALS",
              "column_id": "numbers0",
              "compare_value": [5]
            }]
          }
        },
        "31933592-171a-47ae-93a5-7a1c214fc9a3": {
          "if": {
            "operator": "AND",
            "groups": [{
              "operator": "ANY_OF",
              "column_id": "status",
              "compare_value": [1]
            }]
          },
          "then": {
            "operator": "AND",
            "groups": [{
              "operator": "IS_NOT_EMPTY",
              "column_id": "text0",
              "compare_value": []
            }]
          }
        }
      }
    }
  }
}
```

{
  "data": {
    "validations": {
      "required_column_ids": null,
      "rules": {
        "80d2c9d3-c93d-40be-9d34-b611241345b5": {
          "then": {
            "operator": "AND",
            "groups": [{
              "operator": "GREATER_THAN_OR_EQUALS",
              "column_id": "numbers0",
              "compare_value": [5]
            }]
          }
        },
        "31933592-171a-47ae-93a5-7a1c214fc9a3": {
          "if": {
            "operator": "AND",
            "groups": [{
              "operator": "ANY_OF",
              "column_id": "status",
              "compare_value": [1]
            }]
          },
          "then": {
            "operator": "AND",
            "groups": [{
              "operator": "IS_NOT_EMPTY",
              "column_id": "text0",
              "compare_value": []
            }]
          }
        }
      }
    }
  }
}


### NOTE

In the query response, conditional rules include both
if
and
then
keys. Validation rules (without a condition) only have a
then
key (the
if
key is absent, not
null
). This differs from the mutation response where
if
is explicitly
null
.

Not all operators work with all column types. Here's a summary of supported combinations for validation rules (without an
if
clause):


| Column Type | ANY_OF | NOT_ANY_OF | GREATER_THAN | GREATER_THAN_OR_EQUALS | LOWER_THAN | LOWER_THAN_OR_EQUAL | BETWEEN | CONTAINS_TEXT | STARTS_WITH_TEXT | NOT_CONTAINS_TEXT |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Status | ✅ | ✅ | — | — | — | — | — | — | — | — |
| Numbers | — | — | ✅ | ✅ | ✅ | ✅ | — | — | — | — |
| Text | — | — | — | — | — | — | — | ✅ | ✅ | ✅ |
| Date | — | — | ✅ | — | — | — | ✅ | — | — | — |
| Rating | ✅ | — | — | — | — | — | — | — | — | — |

For conditional rules, the
if
and
then
clauses additionally support
IS_NOT_EMPTY
across column types. The
then
clause also supports
IS_EMPTY
. The
if
clause supports
EQUALS
and
NOT_EQUALS
for numbers columns.


| Constraint | Description |
| --- | --- |
| One validation rule per column | A column can have at most one validation rule (without an
if
clause). |
| No mixing rule types | A column cannot have both validation rules and conditional rules. |
| Single
if
constraint | Conditional rules must have exactly one constraint in the
if
clause. |
| Single
then
for validation rules | Validation rules (without an
if
clause) must have exactly one constraint in the
then
clause. |
| Multiple
then
for conditional | Conditional rules can have multiple constraints in the
then
clause. |
| Pro/Enterprise only | Validation rules require a Pro or Enterprise plan. |
| Enforced in UI and API | Rules are enforced in both the monday.com UI and via the API. API requests that violate rules return a
DATA_VALIDATIONS_ERROR
(422). |

The
compare_value
array format varies by column type:


| Column Type | Operator | compare_value | Notes |
| --- | --- | --- | --- |
| Status | ANY_OF | [1, 2] | Label indices as integers |
| Numbers | GREATER_THAN | [5] | Single numeric value |
| Text | CONTAINS_TEXT | ["search term"] | Single string |
| Date | BETWEEN | ["2026-01-01", "2026-12-31"] | Two date strings in YYYY-MM-DD |
| Date | GREATER_THAN | ["EXACT", "2026-01-01"] | Prefix with
"EXACT"
for exact date |
| Rating | ANY_OF | [4, 5] | Rating values as integers |
| Any | IS_EMPTY | (omit or empty) | No compare_value needed |
| Any | IS_NOT_EMPTY | (omit or empty) | No compare_value needed |

- Validations reference
— Full query and mutation documentation
- Validations other types
— Input types, enums, and operator details
- Columns reference
— Column types and IDs
If you have questions, post them in the
monday developer community
.

Updated
about 1 month ago


---

# Version

Source: https://developer.monday.com/api-reference/docs/version

Updated
about 2 months ago

Updated
about 2 months ago


---

# Versions

Source: https://developer.monday.com/api-reference/docs/versions

Updated
about 2 months ago

Updated
about 2 months ago


---

# Workspaces

Source: https://developer.monday.com/api-reference/docs/workspaces

Updated
about 1 month ago

Updated
about 1 month ago


---

# About the API Reference

Source: https://developer.monday.com/api-reference/reference/about-the-api-reference

Updated
about 1 month ago

Updated
about 1 month ago


---

# App subscriptions

Source: https://developer.monday.com/api-reference/reference/app-subscriptions

Updated
2 months ago

Updated
2 months ago


---

# Boards

Source: https://developer.monday.com/api-reference/reference/boards

Updated
about 1 month ago

Updated
about 1 month ago


---

# Column Types

Source: https://developer.monday.com/api-reference/reference/column-types-reference

Updated
about 2 months ago

Updated
about 2 months ago


---

# Column values

Source: https://developer.monday.com/api-reference/reference/column-values-v2

Updated
about 2 months ago

Updated
about 2 months ago


---

# Columns

Source: https://developer.monday.com/api-reference/reference/columns

Updated
2 months ago

Updated
2 months ago


---

# Complexity

Source: https://developer.monday.com/api-reference/reference/complexity

Updated
2 months ago

Updated
2 months ago


---

# Connect Boards

Source: https://developer.monday.com/api-reference/reference/connect

Updated
about 2 months ago

Updated
about 2 months ago


---

# Dashboards and widgets

Source: https://developer.monday.com/api-reference/reference/dashboards-and-widgets

Updated
2 months ago

Updated
2 months ago


---

# Document blocks V2

Source: https://developer.monday.com/api-reference/reference/document-blocks-v2

Updated
4 months ago

Updated
4 months ago


---

# Formula

Source: https://developer.monday.com/api-reference/reference/formula

Updated
about 2 months ago

Updated
about 2 months ago


---

# Items page

Source: https://developer.monday.com/api-reference/reference/items-page

Updated
about 2 months ago

Updated
about 2 months ago


---

# Platform API

Source: https://developer.monday.com/api-reference/reference/platform-api

Updated
2 months ago

Updated
2 months ago


---

# Search

Source: https://developer.monday.com/api-reference/reference/search

Updated
3 days ago

Updated
3 days ago


---

# Users

Source: https://developer.monday.com/api-reference/reference/users

Updated
22 days ago

Updated
22 days ago


---

# Other types

Source: https://developer.monday.com/api-reference/reference/users-other-types

Updated
22 days ago

Updated
22 days ago


---

# Validations

Source: https://developer.monday.com/api-reference/reference/validations

Updated
about 1 month ago

Updated
about 1 month ago


---

# Other types

Source: https://developer.monday.com/api-reference/reference/validations-other-types

Updated
about 1 month ago

Updated
about 1 month ago


---
