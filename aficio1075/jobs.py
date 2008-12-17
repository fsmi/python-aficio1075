# -*- coding: utf-8 -*-
# vim:set ft=python ts=4 sw=4 noet:

# aficio1075/jobs.py -- Adapter for the HTTP / HTML interface to print job
#   control of Ricoh Aficio 1075
#
# Copyright (C) 2008 Fabian Knittel <fabian.knittel@fsmi.uni-karlsruhe.de>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301  USA.

import urllib
from StringIO import StringIO
import xml.etree.ElementTree as ET
import tidy
import weakref

def parse_html(html_str):
	xhtml_str = tidy.parseString(html_str, output_xhtml = 1, indent = 1,
			numeric_entities = 1, add_xml_decl = 1, tidy_mark = 1)
	return ET.parse(StringIO(xhtml_str))

def xhtml_tag(tag):
	return '{http://www.w3.org/1999/xhtml}%s' % tag


class Job(object):
	def __init__(self, *args, **kwargs):
		self.id = kwargs.get('id')
		self.user_name = kwargs.get('user_name')
		self.doc_name = kwargs.get('doc_name')
		self.status = kwargs.get('status')
		self.pages = kwargs.get('pages')
		self.size = kwargs.get('size')

	def __repr__(self):
		return "<%s(id = %s, user_name = %s, doc_name = %s, " \
				"status = %s, pages = %s, size = %s)>" % \
				(self.__class__.__name__, self.id,
				self.user_name,	self.doc_name, self.status,
				self.pages, self.size)


class JobList(object):
	def __init__(self, *args, **kwargs):
		self.base_url = 'http://%s' % kwargs['host']
		self.jobs = None
		self.refresh()

	def refresh(self):
		u = urllib.urlopen("%s/manage_job.cgi" % self.base_url)
		tree = parse_html(u.read())
		u.close()
		job_rows = tree.find('/%s/%s/%s/%s/%s' % (xhtml_tag('body'),
				xhtml_tag('table'), xhtml_tag('tr'),
				xhtml_tag('td'), xhtml_tag('table')))
		self.jobs = map(self.__parse_job_row, job_rows[1:])

	def __parse_job_row(self, job_row):
		assert len(job_row) == 7
		return Job(id = job_row[0].text.strip(),
				user_name = job_row[1].text.strip(),
				doc_name = job_row[3].text.strip(),
				status = job_row[4].text.strip(),
				pages = job_row[6].text.strip())


class WaitingJob(Job):
	def __init__(self, *args, **kwargs):
		super(WaitingJob, self).__init__(*args, **kwargs)
		self.queue = kwargs['queue']

	def cancel(self):
		self.queue.cancel_job(self.doc_name)

class JobCancelFailed(RuntimeError):
	pass

class WaitingJobList(JobList):
	def __init__(self, *args, **kwargs):
		super(WaitingJobList, self).__init__(*args, **kwargs)
		self.passwd = kwargs.get('passwd', None)

	def cancel_all_jobs(self):
		for job in self.jobs.values()[:]:
			job.cancel()

	def cancel_job(self, doc_name):
		if self.passwd is None:
			raise JobCancelFailed("Missing authentication")
		u = urllib.urlopen("%s/del_joblist.cgi" % self.base_url,
				urllib.urlencode([('passwd', self.passwd),
						('del', 'L&ouml;schen'),
						('0', 'ON'), ('id', doc_name)]))
		raw_html = u.read()
		u.close()
		# Use HTML output to refresh the list and check whether the
		# operation was successful.
		tree = parse_html(raw_html)
		job_rows = self.__get_job_rows(tree)
		if job_rows is None:
			raise JobCancelFailed(doc_name, raw_html)
		self.jobs = map(self.__parse_job_row, job_rows[1:])

	def __parse_job_row(self, job_row):
		assert len(job_row) == 6
		return WaitingJob(queue = weakref.proxy(self),
				doc_name = job_row[0].text.strip(),
				user_name = job_row[1].text.strip(),
				status = job_row[3].text.strip(),
				size = job_row[4].text.strip())

	def __get_job_rows(self, tree):
		return tree.find('/%s/%s/%s/%s/%s/%s/%s/%s/%s' % (
				xhtml_tag('body'), xhtml_tag('table'),
				xhtml_tag('tr'), xhtml_tag('td'),
				xhtml_tag('form'), xhtml_tag('table'),
				xhtml_tag('tr'), xhtml_tag('td'),
				xhtml_tag('table')))

	def refresh(self):
		u = urllib.urlopen("%s/manage_joblist.cgi" % self.base_url)
		raw_html = u.read()
		u.close()
		tree = parse_html(raw_html)
		job_rows = self.__get_job_rows(tree)
		self.jobs = map(self.__parse_job_row, job_rows[1:])

