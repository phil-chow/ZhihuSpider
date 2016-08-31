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
    mongoclient = pymongo.MongoClient('127.0.0.1', 27017)
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
        print "GET THIS GUY: --> ", userid
        followee_url = "https://www.zhihu.com/people/" + userid + "/followees"
        response = self.session.get(followee_url, headers=self.headers, cookies=self.cookies).content
        # print response
        if response is None:
            response = self.session.get(followee_url, headers=self.headers, cookies=self.cookies, timeout=7).content
        page = etree.HTML(response)
        # 获取用户信息
        if self.userinfo_db.find_one({"uid": userid}):
            pass
        else:
            self.getuserinfo(userid, page)
        try:
            user_urls = page.xpath('//span[@class="author-link-line"]/a[@class="zg-link author-link"]/@href')
            # 获取用户的hash_id，用于动态获取更多关注人
            hash_id = page.xpath('//div[@class="zm-profile-header-op-btns clearfix"]/button/@data-id')[0]
            # 获取关注数®
            followee_num = int(page.xpath('//div[@class="zm-profile-side-following zg-clear"]/a[1]/strong/text()')[0])
            # print hash_id, followee_num, user_urls
        except IndexError:
            return
        for u_url in user_urls:
            followee_id = u_url.split('/')[-1]
            print "--| ", followee_id
            self.usership_db.update({"uid": userid}, {"$addToSet": {"followee": followee_id}}, upsert=True)
            self.usership_db.update({"uid": followee_id}, {"$addToSet": {"follower": userid}}, upsert=True)
        if followee_num > 20:
            pages = followee_num / 20 + 1
            offset_list = [x*20 for x in xrange(1, pages)]
            if pages > 5:
                offset_list_split = self.splitlist(offset_list, 5)
                threadlist = list()
                for offsets in offset_list_split:
                    t = threading.Thread(target=self.dopro_thread, args=(offsets, userid, hash_id,))
                    threadlist.append(t)
                for t in threadlist:
                    t.setDaemon(True)
                    time.sleep(0.1)
                    t.start()
            else:
                self.dopro_thread(offset_list, userid, hash_id)
        self.usership_db.update({"uid": userid}, {"$set": {"followed": 1}})

    def dopro_thread(self, offsets, userid, hashid):
        for offset in offsets:
            self.doprofiles(offset, userid, hashid)

    # 动态获取“更多”里面的内容
    def doprofiles(self, offset, userid, hash_id):
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
            'Content-Length': '132',
            'Cookie': 'q_c1=7e569ff0fdb944fa9213a3149be8b52d|1472383585000|1472383585000; l_cap_id="ZDk5OTFjYWI5YjZkNGQ5NjlmYTZlZjcwOTNlMTU4MmI=|1472517294|b426487ad604d4051ec290b8a929a6a47ce02a0a"; cap_id="ZmFlYmVhYzY3YjQ3NDNhYjlhOTk4YzQ4YzNkYTY3Mzc=|1472517294|17bcded54321d6f53929721c0fc0bd6b9364f8c8"; d_c0="ABBAVU9NdAqPTvq1sQQDO46t11t_-w7p5Bc=|1472383586"; __utma=51854390.1216087745.1472467394.1472517280.1472524562.4; __utmz=51854390.1472524562.4.3.utmcsr=zhihu.com|utmccn=(referral)|utmcmd=referral|utmcct=/people/Phil_Chow; _za=c900c944-921f-497f-bba0-5978db428ab5; _zap=fb20b074-7c38-4bce-a0fc-d7c6cba18fb1; login="MGMxYzE2ZjkxNDNmNDFjOTgzMDU2MGE3NjlmYTNmODI=|1472517309|3e260a68fec09d3123acfc3b4b0dc043b3bf5c2b"; _xsrf=187ef073f29c851129ae42543d18582e; __utmv=51854390.100-1|2=registration_date=20151202=1^3=entry_date=20151202=1; __utmc=51854390; n_c=1; a_t="2.0ABCMzsm3FwkXAAAADX7sVwAQjM7JtxcJABBAVU9NdAoXAAAAYQJVTb1h7FcAhESn10FY6Wff0MVuCcoWI15zkc-FRVAT9NTK-SyFH68_Lakl9TOHIQ=="; z_c0=Mi4wQUJDTXpzbTNGd2tBRUVCVlQwMTBDaGNBQUFCaEFsVk52V0hzVndDRVJLZlhRVmpwWjlfUXhXNEp5aFlqWG5PUnp3|1472524557|15559b2c4e39c45eb6333210f18c7f8d322b067e; __utmb=51854390.2.10.1472524562; __utmt=1'
        }
        xsrf = '187ef073f29c851129ae42543d18582e'
        # 计算页数，获取更多里面的关注者信息
        params = json.dumps({"offset": offset, "order_by": "created", "hash_id": hash_id})
        payload = {"method": "next", "params": params, "_xsrf": xsrf}
        content = self.session.post("https://www.zhihu.com/node/ProfileFolloweesListV2", headers=thisheader, data=payload).content
        # print content
        try:
            load = json.loads(content)
            lists = load['msg']
            for item in lists:
                try:
                    # print item
                    userpeople = re.search(r'people/[\w+\d+-]+', item)
                    # print userpeople
                    if userpeople is not None:
                        people = userpeople.group()
                        followee_id = people.split('/')[-1]
                        print "---| ", followee_id
                        self.usership_db.update({"uid": userid}, {"$addToSet": {"followee": followee_id}}, upsert=True)
                        self.usership_db.update({"uid": followee_id}, {"$addToSet": {"follower": userid}}, upsert=True)
                except AttributeError:
                    print "ERROR IN DoProfiles"
        except ValueError:
            pass

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
            self.userinfo_db.insert(user_info)
        except etree.XMLSyntaxError:
            print "XMLSynError-----", userid
        except IndexError:
            print "IndexError------", userid
            if page.xpath('//div[@class="page"]/div/@class')[0] == "error":
                self.usership_db.remove({"uid": userid})
                print "%s is removed!" % userid

    def notfollowed(self):
        # followed不等于1
        not_followed = self.usership_db.find({"followed": {"$ne": 1}}, {"_id": 0, "uid": 1}).limit(1000)
        # need_search = [not_id["uid"] for not_id in not_followed]
        # userinfo single use
        userinfoed = [usered["uid"] for usered in self.userinfo_db.find({}, {"_id": 0, "uid": 1})]
        userinfo_need_search = [not_id["uid"] for not_id in not_followed if not_id["uid"] not in userinfoed]
        need_search_list = self.splitlist(userinfo_need_search, 5)
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
            # userinfo and usership
            # t = threading.Thread(target=self.usersearch, args=(user_list,))
            # userinfo single
            t = threading.Thread(target=self.singleuserinfo, args=(user_list,))
            threadlist.append(t)
        return threadlist

    def usersearch(self, userlist):
        for uid in userlist:
            self.getusership(uid)

    def singleuserinfo(self, userlist):
        for uid in userlist:
            print "GET THIS GUY: --> ", uid
            userinfo_url = "https://www.zhihu.com/people/" + uid
            response = self.session.get(userinfo_url, headers=self.headers, cookies=self.cookies).content
            # print response
            if response is None:
                response = self.session.get(userinfo_url, headers=self.headers, cookies=self.cookies, timeout=7).content
            page = etree.HTML(response)
            # 获取用户信息
            if self.userinfo_db.find_one({"uid": uid}):
                continue
            else:
                self.getuserinfo(uid, page)


if __name__ == '__main__':
    uandf = UserinfoAndFollowee()
    # uandf.getusership('Phil_Chow')
    need_search_list = uandf.notfollowed()
    # uandf.usersearch(need_search_list)
    threads = uandf.make_threads(need_search_list)
    for th in threads:
        th.setDaemon(True)
        time.sleep(0.1)
        th.start()
    th.join()
