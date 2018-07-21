## Claim Post

Url: /claim

Method: POST

Accepted JSON fields:

| Field Name      | Required | Content                      |
|-----------------|----------|------------------------------|
| api_key         | Yes      | String; the api key          |
| post_id         | Yes      | String; the Redis post id    |
| debug           | No       | Int; debug to fixed output   |

## Done Post

Url: /done

Method: POST

Accepted JSON fields:

| Field Name      | Required | Content                      |
|-----------------|----------|------------------------------|
| api_key         | Yes      | String; the api key          |
| post_id         | Yes      | String; the post id          |
| debug           | No       | Int; debug to fixed output   |

## Unclaim Post

Url: /unclaim

Method: POST

Accepted JSON fields:

| Field Name      | Required | Content                      |
|-----------------|----------|------------------------------|
| api_key         | Yes      | String; the api key          |
| post_id         | Yes      | String; the post id          |
| debug           | No       | Int; debug to fixed output   |

## Create Keys

Admin only endpoint

Url: /keys/create

Method: POST

Accepted JSON fields:

| Field Name    | Required | Content                      |
|---------------|----------|------------------------------|
| api_key       | Yes      | String; the api key(admin)   |
| username      | Yes      | String; the user's name      |
| is_admin      | No       | Boolean; is an admin or not  |

## My Key

Url: /keys/me

Method: POST

Accepted JSON fields:

| Field Name      | Required | Content                      |
|-----------------|----------|------------------------------|
| api_key         | Yes      | String; the api key(admin)   |

## Revoke Key

Admin only endpoint

Url: /keys/revoke

Method: POST

Accepted JSON fields:

| Field Name      | Required | Content                      |
|-----------------|----------|------------------------------|
| api_key         | Yes      | String; the api key          |
| revoked_key     | Yes      | String; the key to revoke    |

## User Lookup

Url: /user/lookup

Method: POST

Accepted JSON fields:

| Field Name      | Required | Content                      |
|-----------------|----------|------------------------------|
| api_key         | Yes      | String; the api key          |
| username        | Yes      | String; the user's name      |

## User Create

Url: /user/create

Method: POST

Accepted JSON fields:

| Field Name      | Required | Content                            |
|-----------------|----------|------------------------------------|
| api_key         | Yes      | String; the api key                |
| username        | Yes      | String; the user's username        |
| password        | Yes      | String; the user's hashed password |

## API Index

Url: /

Method: POST

Accepted JSON fields:

| Field Name      | Required | Content                      |
|-----------------|----------|------------------------------|
| api_key         | Yes      | String; the api key          |
