from youtubesearchpython import CustomSearch

cs = CustomSearch("ple ordinari", "EgIwAQ%3D%3D", 50)

res = cs.result()

for video in res['result']:
    print(video['title'])

cs._next()


res = cs.result()

for video in res['result']:
    print(video['title'])