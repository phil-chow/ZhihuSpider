# -*- coding: utf-8 -*-

import pymongo
import requests
from lxml import etree
import ConfigParser
import re
import json
import threading
import time


class UserinfoAndFollowee(object):
    session = requests.session()
    cf = ConfigParser.ConfigParser()
    cf.read('config.ini')
    cookies = cf.items('cookies')
    cookies = dict(cookies)
    mongoclient = pymongo.MongoClient()
    db = mongoclient.zhihu
    userinfo_db = db.userinfo
    usership_db = db.usership
    headers = {
        "Host": "www.zhihu.com",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.11; rv:48.0) Gecko/20100101 Firefox/48.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3",
        "Connection": "keep-alive",
        "Referer": "http://www.zhihu.com/oauth/callback/sina?state=04c9325f0f09f97ff480cba34c4c5e40&code=b2214d37d2dfdc350707699a74c13b42"
    }

    # 用户关系
    def getusership(self, userid):
        followee_url = "https://www.zhihu.com/people/" + userid + "/followees"
        response = self.session.get(followee_url, headers=self.headers, cookies=self.cookies).content
        # print response
        if response is None:
            response = self.session.get(followee_url, headers=self.headers, cookies=self.cookies, timeout=7).content
        page = etree.HTML(response)
        # 获取用户信息
        self.getuserinfo(userid, page)
        user_urls = page.xpath('//h2/a[@class="zg-link"]/@href')
        # 获取用户的hash_id，用于动态获取更多关注人
        hash_id = page.xpath('//div[@class="zm-profile-header-op-btns clearfix"]/button/@data-id')[0]
        # 获取关注数®
        followee_num = page.xpath('//div[@class="zm-profile-side-following zg-clear"]/a[1]/strong/text()')
        for u_url in user_urls:
            followee_id = u_url.split('/')[-1]
            self.usership_db.update({"uid": userid}, {"addToSet": {"followee": followee_id}})
            self.usership_db.update({"uid": followee_id}, {"addToSet": {"follower": userid}})
        if followee_num > 20:
            self.doprofiles(followee_num, userid, hash_id)
        self.usership_db.update({"uid": userid}, {"$set": {"followed": 1}})

    # 动态获取“更多”里面的内容
    def doprofiles(self, attention, userid, hash_id):
        url = "https://www.zhihu.com/people/" + userid + "/followees"
        thisheader = {
            'Host': 'www.zhihu.com',
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/43.0.2357.124 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache',
            'Referer': url,
            'Content-Length': 171,
            'Cookie': '''q_c1=f44da6a964464772a161717043512f25|1461649262000|1448978310000;
                        __utma=51854390.317546768.1448978340.1462496554.1462501618.11;
                        __utmz=51854390.1462501618.11.2.utmcsr=zhihu.com|utmccn=(referral)|utmcmd=referral|utmcct=/people/zhang-jia-wei;
                        __utmv=51854390.100-2|2=registration_date=20151202=1^3=entry_date=20151201=1;
                        _za=7f4faaab-c605-4466-9229-3d2d9a8a1390;
                        z_c0=Mi4wQUJDTXpzbTNGd2tBTUFCbkhsblVDUmNBQUFCaEFsVk5mWXhHVndBdDlnTUN4REVtZEM2eVV4ZmtCLTNPRXZqQnpn|1461649277|551a373c4b185768c45727b7cfccc4dcff1e0ef4;
                        cap_id="ZTQ0YTg0YmFlZTVkNGQyMWFlMTU1ZGU3YWQyYWU3ZmY=|1461649262|8bdfc73731a99086ad05126d2c826531d603b1c4";
                        l_cap_id="NGJmNGQ2MTMyMzM1NDFkNTkzNDQ2ZTY1YWIzNWRhZjc=|1461649262|8477a56202c48f485ae9031347e5d2e63629d1cd";
                        d_c0="ADAAZx5Z1AmPTtV0LZd9nuJSFQguxPEVfSw=|1461649263";
                        _zap=c3effcd9-9a0f-407b-be36-5a4ccccb5500;
                        login="YmQ3OWRlYmNjZWFiNGZjYzhjMDJkZDY3YTU2NTYwNWY=|1461649277|5ff75a661eacdf93d8e1bbe3678920d9a8ed8ce3";
                        _xsrf=6a26f87695284ea5088220cd64f70f3a;
                        __utmc=51854390;
                        __utmb=51854390.6.10.1462501618; __utmt=1'''
        }
        xsrf = '6a26f87695284ea5088220cd64f70f3a'
        # 计算页数，获取更多里面的关注者信息
        pages = attention / 20 + 1
        for x in xrange(1, pages):
            offset = x * 20
            params = json.dumps({"offset": offset, "order_by": "created", "hash_id": hash_id})
            payload = {"method": "next", "params": params, "_xsrf": xsrf}
            content = self.session.post("https://www.zhihu.com/node/ProfileFolloweesListV2", headers=thisheader,
                                        data=payload).content
            try:
                load = json.loads(content)
                lists = load['msg']
            except ValueError:
                continue
            for item in lists:
                try:
                    # print item
                    userpeople = re.search(r'people/[\w+\d+-]+', item)
                    print userpeople
                    if userpeople is not None:
                        people = userpeople.group()
                        followee_id = people.split('/')[-1]
                        self.usership_db.update({"uid": userid}, {"addToSet": {"followee": followee_id}})
                        self.usership_db.update({"uid": followee_id}, {"addToSet": {"follower": userid}})
                except AttributeError:
                    print "ERROR IN DoProfiles"

    # 获取用户基本信息
    def getuserinfo(self, userid, page):
        try:
            username = page.xpath('//div[@class="title-section ellipsis"]/span[@class="name"]/text()')
            location = page.xpath('//div[@data-name="location"]/span/span[@class="location item"]/@title')
            business = page.xpath('//div[@data-name="location"]/span/span[@class="business item"]/@title')
            gendertit = page.xpath('//div[@data-name="location"]/span/span[@class="item gender"]/i/@class')
            if len(gendertit)==0:
                gender = 'notsure'
            elif re.search(r'female', gendertit[0]):
                gender = u'女'
            else:
                gender = u'男'
            employment = page.xpath('//div[@data-name="employment"]/span/span[@class="employment item"]/@title')
            position = page.xpath('//div[@data-name="employment"]/span/span[@class="position item"]/@title')
            education = page.xpath('//div[@data-name="education"]/span/span[@class="education item"]/@title')
            college = page.xpath('//div[@data-name="education"]/span/span[@class="education-extra item"]/@title')
            followee = page.xpath('//div[@class="zm-profile-side-following zg-clear"]/a[1]/strong/text()')
            follower = page.xpath('//div[@class="zm-profile-side-following zg-clear"]/a[2]/strong/text()')
            question_num = int(page.xpath('//div[@class="profile-navbar clearfix"]/a[2]/span/text()')[0])
            answer_num = int(page.xpath('//div[@class="profile-navbar clearfix"]/a[3]/span/text()')[0])
            agree_num = int(page.xpath('//span[@class="zm-profile-header-user-agree"]/strong/text()')[0])
            thanks_num = int(page.xpath('//span[@class="zm-profile-header-user-thanks"]/strong/text()')[0])

            if len(username) == 0:
                username = None
            else:
                username = username[0]
            if len(location) == 0:
                location = None
            else:
                location = location[0]
            if len(business) == 0:
                business = None
            else:
                business = business[0]
            if len(employment) == 0:
                employment = None
            else:
                employment = employment[0]
            if len(position) == 0:
                position = None
            else:
                position = position[0]
            if len(education) == 0:
                education = None
            else:
                education = education[0]
            if len(college) == 0:
                college = None
            else:
                college = college[0]
            if len(followee) == 0:
                followee = None
            else:
                followee = int(followee[0])
            if len(follower) == 0:
                follower = None
            else:
                follower = int(follower[0])

            user_info = {"uid": userid, "username": username, "gender": gender, "location": location,
                         "business": business, "employment": employment, "position": position,
                         "education": education, "college": college, "followee": followee,
                         "follower": follower, "question_num": question_num, "answer_num": answer_num,
                         "agree_num": agree_num, "thanks_num": thanks_num
                         }
            if self.userinfo_db.find_one({"uid": userid}):
                self.userinfo_db.update({"uid": userid}, {"$set": user_info})
            else:
                self.userinfo_db.insert(user_info)
        except etree.XMLSyntaxError:
            print "XMLSynError-----", userid
        except IndexError:
            print "IndexError------", userid

    def notfollowed(self):
        # followed不等于1
        not_followed = self.usership_db.find({"followed": {"$ne": 1}}, {"_id": 0, "uid": 1})
        need_search = [not_id["uid"] for not_id in not_followed]
        need_search_list = self.splitlist(need_search, 5)
        return need_search_list

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

    def make_threads(self, search_list):
        threadlist = []
        length = len(search_list)
        for i in range(length):
            user_list = search_list[i]
            t = threading.Thread(target=self.usersearch, args=(user_list,))
            threadlist.append(t)
        return threadlist

    def usersearch(self, user_list):
        for uid in user_list:
            self.getusership(uid)


if __name__ == '__main__':
    uandf = UserinfoAndFollowee()
    uandf.getusership('Phil_Chow')
    need_search_list = uandf.notfollowed()
    threads = uandf.make_threads(need_search_list)
    for th in threads:
        th.setDaemon(True)
        time.sleep(0.1)
        th.start()
