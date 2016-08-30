# -*- coding: utf-8 -*-

import requests, json, re
import ConfigParser, datetime, time
from lxml import etree
import pymongo
import threading


class UserActivity(object):
    session = requests.session()
    cf = ConfigParser.ConfigParser()
    cf.read('config.ini')
    cookies = cf.items('cookies')
    cookies = dict(cookies)
    header = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/43.0.2357.124 Safari/537.36',
        'Host': 'www.zhihu.com',
        'Referer': 'http://www.zhihu.com/'
    }
    mongoclient = pymongo.MongoClient('127.0.0.1', 27017)
    db = mongoclient.zhihu
    user_collection = db.userinfo
    user_acticity = db.useractivity
    user_searched = db.usersearched
    bigvlist = []
    flag = 0

    def create_session(self):
        res = self.session.get('http://www.zhihu.com/', headers=self.header, cookies=self.cookies)
        with open('login2.html', 'w') as fp:
            fp.write(res.content)

    def getbigv(self):
        timedelta = datetime.timedelta(hours=10)
        timescale = datetime.datetime.now() - timedelta
        usersearched = [sd["uid"] for sd in self.user_searched.find({"time": {"$gt": timescale}}, {"uid": 1, "_id": 0})]
        bigvs = self.user_collection.find({"follower": {"$gt": 5000}, "answer_num": {"$gt": 20}}, {"uid": 1, "_id": 0})
        self.bigvlist = [keys["uid"] for keys in bigvs if keys["uid"] not in usersearched]

    # 首页问题和文章动态存入mongodb
    def insertpora(self, qora_url, qora_time, qora, userid):
        if len(qora_url) > 0 and len(qora_url) == len(qora_time):
            for i in range(len(qora_url)):
                nochange = self.user_acticity.find_one({"uid": userid, "time": qora_time[i]})
                # nochange = False
                if nochange:
                    return
                else:
                    if qora == "q":
                        question_re = re.search(r'question/\d+', qora_url[i])
                        answer_re = re.search(r'answer/\d+', qora_url[i])
                        answer = answer_re.group()
                        aid = answer.split('/')[-1]
                    else:
                        question_re = re.search(r'question/\d+', qora_url[i])
                        aid = ""
                    question = question_re.group()
                    qid = question.split('/')[-1]
                    question_info = {"qid": qid, "uid": userid, "aid": aid, "time": qora_time[i], "qora": qora}
                    print userid, qid, aid
                    self.user_acticity.insert(question_info)

    def getquestionid(self, userid):
        self.flag += 1
        print self.flag
        activity_url = "http://www.zhihu.com/people/" + userid
        try:
            response = self.session.get(activity_url, headers=self.header, cookies=self.cookies).content
            page = etree.HTML(response)
            # answer or vote questions
            question_url = page.xpath('//div[@data-type="a"]/div/a[@class="question_link"]/@href')
            question_time = page.xpath('//div[@data-type="a"]/@data-time')
            # member follow  question
            mfq_url = page.xpath(
                '//div[@data-type-detail="member_follow_question"]/div/a[@class="question_link"]/@href')
            mfq_time = page.xpath('//div[@data-type-detail="member_follow_question"]/@data-time')
            # member ask question
            maq_url = page.xpath('//div[@data-type-detail="member_ask_question"]/div/a[@class="question_link"]/@href')
            maq_time = page.xpath('//div[@data-type-detail="member_ask_question"]/@data-time')
            # write or vote articles
            # 将活动内容存入mongodb中
            self.insertpora(question_url, question_time, 'q', userid)
            self.insertpora(mfq_url, mfq_time, 'qf', userid)
            self.insertpora(maq_url, maq_time, 'qa', userid)
            self.user_searched.insert({"uid": userid, "time": datetime.datetime.now()})
        except etree.XMLSyntaxError:
            pass
        except IndexError:
            pass
        except requests.ConnectionError:
            time.sleep(2)
            self.getquestionid(userid)

    def splitlist(self, listosplit, num):
        list_length = len(listosplit)
        list_single = list_length / num
        splited = []
        for i in range(num):
            if i == (num - 1):
                q_to = list_length
            else:
                q_to = list_single * (i + 1)
            splited.append(listosplit[list_single * i:q_to])
        return splited

    def userinfo_thread(self):
        bigv_lists = self.splitlist(self.bigvlist, 5)
        threadlist = []
        for i in range(5):
            bigvs = bigv_lists[i]
            t = threading.Thread(target=self.bigvsearch, args=(bigvs,))
            threadlist.append(t)
        return threadlist

    def bigvsearch(self, bigv_list):
        for bigv in bigv_list:
            self.getquestionid(bigv)


if __name__ == '__main__':
    useractiv = UserActivity()
    useractiv.create_session()
    useractiv.getbigv()
    user_thread = useractiv.userinfo_thread()
    for t in user_thread:
        print t
        # t.setDaemon(True)
        time.sleep(0.1)
        t.start()
    t.join()
