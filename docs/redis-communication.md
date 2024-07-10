# Redis communication
Basis reference for communication beetween client and CLIP server via Redis

## Requests
`request:images`: Redis list of strings. Strings are JSON dumps with schema
```
 {
    "seq": <sequence number>,
    "url": <image url>
 }
 ```
where seq is sequence number gotten by incrementing `request:count` and url is valid url of an image to encode

---

`request:count`: Redis field, must be incremented for every new request (both image and text)

---

`request:texts`: ...

## Responses
All responses are placed at `response` Redis list and are pickled dicts with schema
```
{
    "seq": <sequence number>,
    "answer": <bytes or string depending on code>,
    "code": "ERROR" | "SUCCESS"
}
```
If `code` is SUCCESS then `answer` is tobytes() encoded numpy array. If `code` is ERROR then `answer` is string, describing the error.
