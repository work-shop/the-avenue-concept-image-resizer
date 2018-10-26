#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import os
import logging
import webapp2
import json
import cloudstorage

from google.appengine.api import images, urlfetch, app_identity
from google.appengine.ext import blobstore

def get_image_url( request ):
    """
    A helper method to extract the url that
    should have been passed to the post request.
    """
    url = request.get( 'url' )
    return url


def get_image_name( url ):
    """
    Given a url, get the corresponding image name
    from the URL path
    """
    split_url = url.split( '=/' )
    image_name = split_url[ len( split_url ) - 1 ]
    # extension = image_name.split('.')
    # extension = extension[ len( extension ) - 1 ]
    extension = ''

    return image_name, 'image/'+extension


def save_image_to_cloudstore( filename, image, content_type ):
    """
    given a filepath and image content, save the image
    as a google cloud storage object, and return its file
    location.
    """
    bucket_name = os.environ.get( 'BUCKET_NAME', app_identity.get_default_gcs_bucket_name() )
    bucket = '/' + bucket_name
    filepath = bucket + '/' + filename

    write_retry_params = cloudstorage.RetryParams( backoff_factor=1.1, initial_delay=0.2, max_delay=5.0, max_retry_period=15 )

    with cloudstorage.open( filepath, 'w', retry_params=write_retry_params ) as cloudstore_file:
        cloudstore_file.write( image )

    return '/gs' + filepath


def generate_serving_key_and_url( filepath ):
    """
    Given a google cloud storage filepath to an image,
    generate a serving url for that image.
    """
    key = blobstore.create_gs_key( filepath )
    img = images.Image( blob_key=key )
    try:
        resize_url = images.get_serving_url( key )
        return key, resize_url

    except Exception as e:
        return 'error: Generic', str( e )




class UploadHandler( webapp2.RequestHandler ):
    def post( self ):
        """
        Handle post requests coming in from Zoho. Zoho is
        expected to pass a POST request to Google when an
        image is created, with a body including the { url: <imageurl> }.
        This routine downloads the image from zoho, and inserts it
        into blob storage.
        """
        try:

            url = get_image_url( self.request )

            result = urlfetch.fetch(url)
            filename, content_type = get_image_name( url )

            #self.response.out.write( result.content )

            if result.status_code == 200:
                #self.response.out.write( result.content )
            #
                image = result.content

                #self.response.out.write( image )

                filepath = save_image_to_cloudstore( filename, image, content_type )
                key, resize_url = generate_serving_key_and_url( filepath )

                # self.response.out.write( json.dumps({ 'success': True, 'urls': filename, 'content_type': content_type, 'filepath': filepath }))
                self.response.out.write( json.dumps({ 'key': key, 'success': True, 'urls': { 'original': url, 'resize_url': resize_url }, 'location': filepath }))
            #
            else:
                self.response.status_int = result.status_code
                self.response.out.write( json.dumps({ 'success': False, 'error': result.status_code, 'message': 'An error was encountered downloading the passed url from zoho.', 'request_url': url }) )



        except urlfetch.Error:
            self.response.status_int = 400
            self.response.out.write( json.dumps({ 'success' : False, 'error': 400, 'message': 'The passed image url was invalid.', 'url': url }) )

        except Exception as e:
            self.response.status_int = 400
            self.response.out.write( json.dumps({ 'success' : False, 'error': 400, 'message': str(e) }) )



app = webapp2.WSGIApplication([
    webapp2.Route(r'/upload', handler=UploadHandler, name='main'),
    # webapp2.Route(r'/<siteName>/webhook-uploads/<imageFile>', handler=MainHandler, name='main'),
    # webapp2.Route(r'/<siteName>/webhook-uploads/<timestamp>/<imageFile>', handler=NewHandler, name='main'),
], debug=False)
