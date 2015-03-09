#!/usr/bin/env python

import urllib
import json
import sqlite3
import time

from gmusicapi import Mobileclient

class Track:
	def __init__(self, artist, song):
		self.artist = artist
		self.song = song
	
	def __repr__(self):
		return "<Track artist:%s song:%s>" % (self.artist, self.song)
		
class HitlistWS:		
	def playlist(self):
		playlistUrl = "http://triplejgizmo.abc.net.au/jjj-hitlist/current/app/webroot/latest/play.txt"
		playlist = []
		
		uh = urllib.urlopen(playlistUrl)
		data = uh.read()
		js = json.loads(str(data))
		
		for entry in js:
			artist = entry['HitlistEntry']['artist']
			song = entry['HitlistEntry']['track']
			playlist.append(Track(artist, song))
			
		return playlist
	
class DbCache:
	def __init__(self, file):
		self.dbFile = file
		
	def open(self):
		self.conn = sqlite3.connect(self.dbFile)
		
		# Create the schema if it doesn't exist
		self.conn.execute("create table if not exists track(id INTEGER PRIMARY KEY AUTOINCREMENT, artist text, song text, ignore integer default false, nid text, unique(artist, song) on conflict ignore)")
		self.conn.execute("create table if not exists playlist(rank integer, track integer, foreign key(track) references track(id))")
				
		self.conn.commit()
		
	def close(self):
		self.conn.close()
			
	def update(self, playlist):
		cur = self.conn.cursor()
		
		cur.execute("delete from playlist")
		
		rank = 0;
		for track in playlist:
			rank+=1
			cur.execute("insert into track(artist, song) values (?, ?)", (track.artist, track.song))
			# Gotta be a better way
			cur.execute("select id from track where artist = ? and song = ?", (track.artist, track.song))
			track_id = cur.fetchone()
			cur.execute("insert into playlist(rank, track) values (?, ?)", (rank, track_id[0]))
					
		cur.close()
		self.conn.commit()
	
	def unmappedTracks(self):
		unmapped = []
		cur = self.conn.cursor()
		
		cur.execute("select artist, song from track where nid is null and ignore = 'false'")
		for row in cur.fetchall():
			unmapped.append(Track(row[0], row[1]))
		
		cur.close()
		
		return unmapped
		
	def storemapping(self, song, artist, nid):
		cur = self.conn.cursor()
		
		cur.execute("update track set nid = ? where artist = ? and song = ?", (nid, artist, song))
				
		cur.close()
		self.conn.commit()
		
	def playlist(self):
		playlist = []
		
		cur = self.conn.cursor()
		
		cur.execute("select t.nid from playlist p join track t on p.track = t.id where nid is not null order by p.rank")
		for row in cur.fetchall():
			playlist.append(row[0])
		
		cur.close()
		
		
		return playlist
	
class GMusicWS:
	def __init__(self, user, password, playlistName):
		self.playlistName = playlistName
		self.api = Mobileclient()
		print "Logging into MobileClient API"
		self.api.login(user, password)

	def mapUnknownTracks(self, db):
		playlist = db.unmappedTracks()
		
		for track in playlist:
			searchstr = track.artist + " " + track.song
			print "Searching for %s" % (searchstr)
			try:
				result = self.api.search_all_access(searchstr, max_results=1)
				print "Found " + result['song_hits'][0]['track']['artist'] + " - " + result['song_hits'][0]['track']['title']
				nid = result['song_hits'][0]['track']['nid']
				db.storemapping(track.song, track.artist, nid)
			except:
				print "Error parsing result: " + str(result)
				
			time.sleep(1)
	
	def maintain(self, tracks):
		print "Searching for playlist %s" % (self.playlistName)
				
		found = False
		searchres = self.api.get_all_playlists()
		for list in searchres:
			if list['name'] == self.playlistName:
				found = True
				pid = list['id']
				
		if not found:
			print "Not found - creating"
			pid = self.api.create_playlist(self.playlistName)
		
		print "Playlist id is %s" % (pid)
		
		print "Getting current contents"
		playlists = self.api.get_all_user_playlist_contents()
		currentEntries = []
		for playlist in playlists:
			if playlist['name'] == self.playlistName:
				for entry in playlist['tracks']:
					currentEntries.append(entry['id'])

		print "Removing songs"		
		self.api.remove_entries_from_playlist(currentEntries)
		
		print "Adding songs"
		self.api.add_songs_to_playlist(pid, tracks)
	
def main():
	db = DbCache("hitlist.db")
	
	db.open()
	
	print "Getting hitlist from WS"
	hitws = HitlistWS()
	playlist = hitws.playlist()
	
	print "Updating DB cache"
	db.update(playlist)

	gws = GMusicWS('user@gmail.com', 'password', 'Triple J Hitlist')
	
	print "Mapping unknown tracks"
	gws.mapUnknownTracks(db)
		
	gws.maintain(db.playlist())
	
	db.close()
	
if __name__ == '__main__':
    main()