import ConfigParser
import sys
import mysql.connector
import datetime
from apiclient.discovery import build
import urllib2
from alchemyapi import AlchemyAPI
alchemyapi = AlchemyAPI()
reload(sys)
sys.setdefaultencoding("utf-8")

# Reading Configuration file
config = ConfigParser.ConfigParser()
config.read('search.ini')
devKey = config.get('cse', 'developerKey')
mysqlpass = config.get('mysql', 'password')
searchengineid = config.get('cse', 'searchengineid')

# Taking two parameters: search key, topic (target)
search_key = sys.argv[1]
topic = sys.argv[2]

service = build('customsearch', 'v1', developerKey=devKey)

# Establish connection with MySQL server
cnx = mysql.connector.connect(user='root', password=mysqlpass,
                              host='127.0.0.1',
                              database='SEME',
                              use_unicode=True)
cursor = cnx.cursor()

# Enforce UTF-8 for the connection.
cursor.execute('SET NAMES utf8mb4')
cursor.execute("SET CHARACTER SET utf8mb4")
cursor.execute("SET character_set_connection=utf8mb4")

# SQL command to be used later to insert record
add_search_result = ("INSERT INTO search_results "
					"(search_term, topic, rank, title, link, content, content_text, sentiment, score, mixed, key_sentiment, key_score, key_mixed, doc_sentiment, doc_score, doc_mixed, date_time) "
					"VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)")

# Outer loop for every 10 of top 100
j = 0
for x in xrange(10):
	request = service.cse().list(
	      q=search_key,
		  cx=searchengineid,
		  start=j + 1,
		)
	response = request.execute()

	# Inner loop for each search result (10 inner loops per 1 outer loop)
	i = 0
	for item in response['items']:
		# Getting full HTML of the web page
		content_HTML = ""
		try:
			sock = urllib2.urlopen(response['items'][i]['link'], timeout=1)
			# Avoid to put into variable if size HTML code is too big
			if sys.getsizeof(sock.read()) < 4098871:
				sock.close()
				sock = urllib2.urlopen(response['items'][i]['link'])
				content_HTML = sock.read()
			sock.close()
		except Exception:
			print j + i + 1, 'urllib error'

		# Targeted sentiment analysis
		sentiment = None
		score = None
		mixed = None
		alchemy_response = alchemyapi.sentiment_targeted('url', response['items'][i]['link'], topic)
		if alchemy_response['status'] == 'OK':
			sentiment = alchemy_response['docSentiment']['type']
			if 'score' in alchemy_response['docSentiment']:
				score = alchemy_response['docSentiment']['score']
			if 'mixed' in alchemy_response['docSentiment']:
				mixed = alchemy_response['docSentiment']['mixed']
		else:
			print j + i + 1, 'Error in targeted sentiment analysis call: ', alchemy_response['statusInfo']

		# Keyword sentiment analysis
		keyword_response = alchemyapi.keywords('url', response['items'][i]['link'], {'sentiment': 1})
		key_sentiment = None
		key_score = None
		key_mixed = None
		if keyword_response['status'] == 'OK':
			if 'keywords' in keyword_response:
				for keyword in keyword_response['keywords']:
					if keyword['text'].lower() == topic.lower():
						if 'sentiment' in keyword:
							key_sentiment = keyword['sentiment']['type']
							if 'score' in keyword['sentiment']:
								key_score = keyword['sentiment']['score']
							if 'mixed' in keyword['sentiment']:
								key_mixed = keyword['sentiment']['mixed']
		else:
			print j + i + 1, 'Error in keyword extaction call: ', keyword_response['statusInfo']

		# Document sentiment analysis
		doc_response = alchemyapi.sentiment('url', response['items'][i]['link'])
		doc_sentiment = None
		doc_score = None
		doc_mixed = None
		if doc_response['status'] == 'OK':
			doc_sentiment = doc_response['docSentiment']['type']
			if 'score' in doc_response['docSentiment']:
				doc_score = doc_response['docSentiment']['score']
			if 'mixed' in doc_response['docSentiment']:
				doc_mixed = doc_response['docSentiment']['mixed']
		else:
		    print  j + i + 1, 'Error in sentiment analysis call: ', doc_response['statusInfo']


		# Getting plain text of the web page
		content_text = ""
		text_response = alchemyapi.text('url', response['items'][i]['link'])
		if text_response['status'] == 'OK':
			content_text = text_response['text']
		else:
			print j + i + 1, 'Error in text extraction call: ', text_response['statusInfo']

		# Getting current data and time
		date_time = datetime.datetime.now()

		# Store data into database
		title = response['items'][i]['title']
		link = response['items'][i]['link']
		
		# Debug code to show size of web page HTML and text
#		print sys.getsizeof(content_HTML)
#		print sys.getsizeof(content_text)
		
		data_result = (search_key, topic, j + i + 1, title, link, content_HTML, content_text, sentiment, score, mixed, key_sentiment, key_score, key_mixed, doc_sentiment, doc_score, doc_mixed, date_time)
		try:
			cursor.execute(add_search_result, data_result)
		except Exception:
			content_HTML = ""
			data_result = (search_key, topic, j + i + 1, title, link, content_HTML, content_text, sentiment, score, mixed, key_sentiment, key_score, key_mixed, doc_sentiment, doc_score, doc_mixed, date_time)
			cursor.execute(add_search_result, data_result)
		print j + i + 1, 'Done'

		# Increment ones digit
		i = i + 1
	# Increment tens digit
	j = j + 10

# Commit transaction of all 100 data insert
cnx.commit()

cursor.close()
cnx.close()
