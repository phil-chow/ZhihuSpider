# -*- coding: utf-8 -*-

import requests
import pymongo
import ConfigParser
import threading
from lxml import etree
import time
import datetime
import sys

reload(sys)
sys.setdefaultencoding("utf-8")


class QuestionInfo(object):
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
    session = requests.session()
    db = mongoclient.zhihu
    user_acticity = db.useractivity
    questiondb = db.questiondb
    answerdb = db.answerdb
    articledb = db.articledb
    question_list = []
    qa_list = []

    def getquestion(self, qid):

        question_url = "https://www.zhihu.com/question/" + qid
        try:
            response = self.session.get(question_url, headers=self.header, cookies=self.cookies).content
            page = etree.HTML(response)
            qname = page.xpath('//div[@id="zh-question-title"]/h2/span/text()')[0]
            qattention_now = int(page.xpath('//div[@class="zh-question-followers-sidebar"]/div/a/strong/text()')[0])
            qread_now = int(page.xpath('//div[@class="zm-side-section-inner"]/div[2]/strong/text()')[0])
            qanswer_now = page.xpath('//div[@class="zh-answers-title clearfix"]/h3/@data-num')
            qupdatetime= datetime.datetime.now()
            if len(qanswer_now) > 0:
                qanswer_num = int(qanswer_now[0])
            else:
                qanswer_num = 1
            insert_info = {"qid": qid, "qname": qname, "qattention": qattention_now, "qanswer_num": qanswer_num,
                           "qread": qread_now, "time": qupdatetime}
            self.questiondb.insert(insert_info)
            print qid, qname, qattention_now, qanswer_num
            # self.nextsearch()
        except UnicodeEncodeError:
            pass
        except IndexError:
            insert_info = {"qid": qid, "qname": "Question may closed", "qattention": None, "qanswer_num": None,
                           "qread": None, "time": None}
            self.questiondb.insert(insert_info)
        except requests.ConnectionError:
            time.sleep(2)
            self.getquestion(qid)

    def getanswers(self, qid, aid):
        answer_url = "https://www.zhihu.com/question/" + qid + "/answer/" + aid
        try:
            response = self.session.get(answer_url, headers=self.header, cookies=self.cookies).content
            page = etree.HTML(response)
            uidhref = page.xpath('//div[@class="answer-head"]/div/a[@class="author-link"]/@href')
            asupports = page.xpath('//div[@class="answer-head"]/div[2]/@data-votecount')
            timenow = datetime.datetime.now()

            if len(uidhref) > 0:
                uid = uidhref[0].split('/')[-1]
            else:
                uid = "anonymous_user"
            if len(asupports) > 0:
                asupport = asupports[0]
            else:
                asupport = None
            insertinfo = {"aid": aid, "uid": uid, "qid": qid, "atime": timenow, "asupport": asupport}
            print uid, aid, asupport
            self.answerdb.insert(insertinfo)
            # self.nextsearch()
        except etree.XMLSyntaxError:
            pass
        except requests.ConnectionError:
            time.sleep(2)
            self.getanswers(qid, aid)
            # self.nextsearch()

    def insert_or_not(self, qid, *aid):
        if aid:
            if self.answerdb.find_one({"qid": qid, "aid": aid[0]}):
                for i in self.answerdb.find({"qid": qid, "aid": aid[0]}, {"atime": 1, "_id": 0}).sort("atime", -1).limit(1):
                    lastime = i["atime"]
                    if self.time_calc(lastime) > 10:
                        return True
                    else:
                        return False
            else:
                return True
        else:
            if self.questiondb.find_one({"qid": qid}):
                for i in self.questiondb.find({"qid": qid}, {"time": 1, "_id": 0}).sort("time", -1).limit(1):
                    lastime = i["time"]
                    if self.time_calc(lastime) > 10:
                        return True
                    else:
                        return False
            else:
                return True

    def time_calc(self, last_time):
        timenow = datetime.datetime.now()
        timedelta = timenow - last_time
        hours = timedelta.days * 24 + timedelta.seconds/3600
        return hours

    def getsearchlist(self):
        # already have in and small than 10 hours
        timedelta = datetime.timedelta(hours=10)
        timescale = datetime.datetime.now() - timedelta
        qhas_in = [q["qid"] for q in self.questiondb.find({"time": {"$gt": timescale}}, {"qid": 1, "_id": 0})]
        qahas_ins = self.answerdb.find({"atime": {"$gt": timescale}}, {"qid": 1, "aid": 1, "_id": 0})
        qahas_in = [(qa["qid"], qa["aid"]) for qa in qahas_ins]

        # question and answer
        timedelta = datetime.timedelta(hours=10)
        timescale = datetime.datetime.now() - timedelta
        q_and_a = self.user_acticity.find({"qora": "q"}, {"qid": 1, "aid": 1, "_id": 0})
        q_list = [keys["qid"] for keys in q_and_a if keys["qid"] not in qhas_in]
        # no repeat question id
        qf_list = self.user_acticity.find({"qora": "qf"}, {"qid": 1, "_id": 0})
        qa_list = self.user_acticity.find({"qora": "qa"}, {"qid": 1, "_id": 0})
        q_list += [qf["qid"] for qf in qf_list if qf["qid"] not in qhas_in]
        q_list += [qa["qid"] for qa in qa_list if qa["qid"] not in qhas_in]
        q_set = set(q_list)
        self.question_list = [i for i in q_set]
        # no repeat qid and aid set
        q_a = self.user_acticity.find({"qora": "q"}, {"qid": 1, "aid": 1, "_id": 0})
        q_a_list = [(qa["qid"], qa["aid"]) for qa in q_a if (qa["qid"], qa["aid"]) not in qahas_in]
        q_a_set = set(q_a_list)
        self.qa_list = [k for k in q_a_set]

    def questionsearch(self, q_only):
        print len(q_only)
        for qid in q_only:
            # if self.insert_or_not(qid):
            self.getquestion(qid)

    def questionanswer(self, q_answer):
        print len(q_answer)
        for q_a in q_answer:
            qid = q_a[0]
            aid = q_a[1]
            # if self.insert_or_not(qid, aid):
            self.getanswers(qid, aid)

    def splitlist(self, listosplit, num):
        list_length = len(listosplit)
        list_single = list_length/num
        splited = []
        for i in range(num):
            if i == (num-1):
                q_to = list_length
            else:
                q_to = list_single*(i+1)
            splited.append(listosplit[list_single*i:q_to])
        return splited

    # 将列表切分多任务完成
    def qid_thread(self):
        question_only_list = self.splitlist(self.question_list, 4)
        question_answer_list = self.splitlist(self.qa_list, 4)
        threadlist = []
        for i in range(4):
            question_only = question_only_list[i]
            question_answer = question_answer_list[i]
            t1 = threading.Thread(target=self.questionsearch, args=(question_only,))
            t2 = threading.Thread(target=self.questionanswer, args=(question_answer,))
            threadlist.append(t1)
            threadlist.append(t2)
        return threadlist

if __name__ == '__main__':
    getquesinfo = QuestionInfo()
    getquesinfo.getsearchlist()
    # getquesinfo.nextsearch()
    question_thread = getquesinfo.qid_thread()
    for t in question_thread:
        print t
        # t.setDaemon(True)
        time.sleep(0.1)
        t.start()
    t.join()
