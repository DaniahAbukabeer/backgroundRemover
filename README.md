# microservice for background removal using rembg
for now, only one "worker" is needed, for the future, we can add more workers to handle more load.


we went with the model birefnet-general-lite since it performed better than the default and took only 6seconds on average to process an image

to change the model change this line in main.py:
```python
session = new_session("birefnet-general-lite")
```
to this 
```python
session = new_session("birefnet-general")
``` 
this a much slower model but the creators metioned its thier strongest, but for my use cases, i found the lite version devlivered better results and was much faster, so i went with it.

# background removal microservice
this microservice is built using fastapi and rembg, it exposes an endpoint /remove-background that accepts a POST request with an image file and returns the image with the background removed.