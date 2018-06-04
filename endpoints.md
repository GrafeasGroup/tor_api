## Claim Post

Url: /Posts/claim

Method: Any

Accepted JSON fields:

| Field Name      | Required | Content                      |
|-----------------|----------|------------------------------|
| api_key         | Yes      | String; the api key          |
| name            | Yes      | String; the user's name      |
| is_admin        | No       | Boolean; is an admin or not  |
| debug           | No       | Int; debug to fixed output   |

## Done Post

Url: /Posts/done

Method: Any

Accepted JSON fields:

| Field Name      | Required | Content                      |
|-----------------|----------|------------------------------|
| api_key         | Yes      | String; the api key          |
| post_id         | Yes      | String; the post id          |
| debug           | No       | Int; debug to fixed output   |

## Unclaim Post

Url: /Posts/unclaim

Method: Any

Accepted JSON fields:

| Field Name      | Required | Content                      |
|-----------------|----------|------------------------------|
| api_key         | Yes      | String; the api key          |
| post_id         | Yes      | String; the post id          |
| debug           | No       | Int; debug to fixed output   |

## Create Keys

Url: /Keys/create

Method: Post

Accepted JSON fields:

| Field Name    | Required | Content                      |
|---------------|----------|------------------------------|
| api_key       | Yes      | String; the api key          |
| name          | Yes      | String; the user's name      |
| is_admin      | No       | Boolean; is an admin or not  |
| admin_api_key | No       | String; the admin api key    |

## My Key

Url: /Keys/me

Method: Post

Accepted JSON fields:

| Field Name      | Required | Content                      |
|-----------------|----------|------------------------------|
| api_key         | Yes      | String; the api key          |

## Revoke Key

Url: /Keys/revoke

Method: Any

Accepted JSON fields:

| Field Name      | Required | Content                      |
|-----------------|----------|------------------------------|
| api_key         | Yes      | String; the api key          |
| revoked_key     | Yes      | String; the key to revoke    |

## User Index

Url: /Users/index

Method: Any

Accepted JSON fields:

| Field Name      | Required | Content                      |
|-----------------|----------|------------------------------|
| api_key         | Yes      | String; the api key          |
| username        | Yes      | String; the user's name      |

## API Index

Url: /API/index

Method: Any

Accepted JSON fields:

| Field Name      | Required | Content                      |
|-----------------|----------|------------------------------|
| total_completed | Yes      | Int; the transcription count |
| total_posted    | Yes      | Int; all posts of a user     |
