# Redis communication
Basis reference for communication beetween client and CLIP server via Redis

## Requests
`request:images`: Redis list of strings. Strings are BSON dumps with schema
```
 {
    "seq": <sequence number>,
    "url": <image url>
 }
 ```
where `seq` is sequence number gotten by incrementing `request:count` and `url` is valid url of an image to encode

---

`request:count`: Redis field, must be incremented for every new request (both image and text)

---

`request:text-flag`: Redis Pub/Sub channel, producer (client) must publish here to notify consumer. Consumer (server) must subscribe and listen on this channel for notifies.

---

`request:texts`: Redis hashtable of strings. Strings are BSON dumps with schema
```
 {
    "seq": <sequence number>,
    "text": <text to encode>
 }
 ```
where `seq` is sequence number gotten by incrementing `request:count`. `text` is just text to encode. Requests are labeles by some unique id of text request thread.

It is assumed that there are several different threads of text requests and for each thread it is necessary to process only the last request.

## Responses
All responses are placed at `response` Redis list and are BSON dumps with schema
```
{
    "seq": <sequence number>,
    "answer": <bytes or string depending on code>,
    "code": "ERROR" | "SUCCESS"
}
```
If `code` is SUCCESS then `answer` is tobytes() encoded numpy array. If `code` is ERROR then `answer` is string, describing the error.
