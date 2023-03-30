from django.shortcuts import render, redirect
from django.http import JsonResponse
import json
from .accounts import *
from .models import * 
import os
from django.conf import settings
import re
import random
from numpy.linalg import norm
from .recommendations import get_image_recommendations, get_recommended_products, get_mean_cart_recommendations
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from math import ceil

@login_required(login_url='userlogin')
def store(request):
    customer = request.user.customer
    order, created = Order.objects.get_or_create(customer=customer, complete=False)
    items = order.orderitem_set.all()
    cartItems = order.get_cart_items

    product_list = ProductTest.objects.all()
    user_preferences = request.user.customer.preferences
    recommended_products = get_recommended_products(product_list, user_preferences)

    # Determine the number of products to show per page
    num_products_per_page = 20
    total_num_products = len(recommended_products)
    remaining_products = total_num_products % num_products_per_page
    if remaining_products == 0:
        num_pages = total_num_products // num_products_per_page
    else:
        num_pages = total_num_products // num_products_per_page + 1

    paginator = Paginator(recommended_products, num_products_per_page)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # If this is the last page, adjust the number of products per page to be equal to the remaining products
    if page_obj.number == num_pages and remaining_products != 0:
        paginator = Paginator(recommended_products, remaining_products)
        page_obj = paginator.get_page(page_number)

    context = {'page_obj': page_obj, 'cartItems': cartItems}
    return render(request, 'store/store.html', context)

@staff_member_required
def delete_product(request, product_id):
    product = ProductTest.objects.get(id=product_id)
    image_path = os.path.join(settings.MEDIA_ROOT, str(product.imageURL))

    # Delete the image file
    if os.path.exists(image_path):
        os.remove(image_path)

    # Delete the product from the database
    product.delete()

    messages.success(request, f"Product {product.productDisplayName} has been deleted.")
    return HttpResponseRedirect(reverse('store'))

def filter_products_by_preferences(product_list, preferences):
    filtered_products = product_list

    for field in ['gender', 'masterCategory', 'subCategory', 'articleType', 'baseColour', 'season', 'year', 'usage']:
        value = getattr(preferences, field, None)
        if value:
            filtered_products = filtered_products.filter(**{field: value})
    
    num_products = 6
    if len(filtered_products) > num_products:
        return random.sample(list(filtered_products), num_products)
    else:
        return filtered_products

@login_required(login_url='userlogin')
def survey(request):
    if request.method == 'POST':
        customer = request.user.customer
        preferences, created = UserPreference.objects.get_or_create(customer=customer)
        
        # Save previous gender preference
        prev_gender = preferences.gender

        for field in ['gender', 'masterCategory', 'subCategory', 'articleType', 'baseColour', 'season', 'year', 'usage']:
            setattr(preferences, field, request.POST.get(field))
        preferences.save()
        customer.preferences = preferences
        customer.save()

        # Update order after saving preferences
        order, _ = Order.objects.get_or_create(customer=customer, complete=False)        

        return redirect('store')

    product_list = ProductTest.objects.all()
    user_preferences = request.user.customer.preferences
    filtered_products = filter_products_by_preferences(product_list, user_preferences)

    context = {'filtered_products': filtered_products, 'user_preferences': user_preferences}
    return render(request, 'store/survey.html', context)

@login_required(login_url='userlogin')
def cart(request):
    customer = request.user.customer
    order, created = Order.objects.get_or_create(customer=customer, complete=False)
    items = order.orderitem_set.all()
    cartItems = order.get_cart_items
    
    filter_type = request.GET.get('filter', 'masterCategory')

    items_by_filter = {}
    recommended_images = {}
    product_image_urls = []

    for item in items:
        items_by_filter.setdefault(getattr(item.product, filter_type), []).append(item)
        recommended_images[str(item.id)] = get_image_recommendations(item.product.id)
        product_image_urls.append(item.product.imageURL)

    user_gender = customer.preferences.gender if customer.preferences and customer.preferences.gender else None

    mean_cart_recommendations = get_mean_cart_recommendations(product_image_urls, gender=user_gender)

    filter_mean_recommendations = {
        filter_value: get_mean_cart_recommendations([item.product.imageURL for item in filter_items], master_category=filter_value if filter_type == 'masterCategory' else None, gender=user_gender, articleType=filter_value if filter_type == 'articleType' else None, subCategory=filter_value if filter_type == 'subCategory' else None)
        for filter_value, filter_items in items_by_filter.items()
    }

    context = {
        'items_by_filter': items_by_filter,
        'filter_type': filter_type,
        'order': order,
        'cartItems': cartItems,
        'recommended_images': recommended_images,
        'filter_mean_recommendations': filter_mean_recommendations,
    }
    return render(request, 'store/cart.html', context)


def get_filtered_products(request):
    if request.method == 'POST':
        customer = request.user.customer
        preferences, created = UserPreference.objects.get_or_create(customer=customer)
        for field in ['gender', 'masterCategory', 'subCategory', 'articleType', 'baseColour', 'season', 'year', 'usage']:
            setattr(preferences, field, request.POST.get(field))
        preferences.save()
        customer.preferences = preferences
        customer.save()
        
        product_list = ProductTest.objects.all()
        filtered_products = filter_products_by_preferences(product_list, preferences)
        
        data = [{
            'id': product.id,
            'name': product.productDisplayName,
            'image_url': product.imageURL,
        } for product in filtered_products]

        return JsonResponse(data, safe=False)


@login_required(login_url='userlogin')
def updateItem(request):
    data = json.loads(request.body)
    product_info = data['productId']
    action = data['action']
    source = data.get('source', '')

    customer = request.user.customer

    if source == 'cart':
        match = re.search(r'(?<=\/images\\).+?(?=.jpg)', product_info)
        if match:
            product_id = int(match.group())
        else:
            product_id = int(product_info)
    else:
        product_id = int(product_info)

    product = ProductTest.objects.get(id=product_id)

    order, created = Order.objects.get_or_create(customer=customer, complete=False)
    orderItem, created = OrderItem.objects.get_or_create(order=order, product=product)

    if action == 'add':
        orderItem.quantity += 1
        orderItem.save()
    elif action == 'remove':
        orderItem.delete()

    return JsonResponse('Item was added', safe=False)