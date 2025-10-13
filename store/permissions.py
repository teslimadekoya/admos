from rest_framework import permissions

class IsAdminOrOwnerOrReadOnly(permissions.BasePermission):
    """
    - Admin/staff can do anything.
    - Authenticated users can create Packs and assign FoodItems.
    - Only the owner of a Pack can update or delete it.
    - Everyone else can only read (GET, HEAD, OPTIONS).
    """

    def has_permission(self, request, view):
        # Anyone can read
        if request.method in permissions.SAFE_METHODS:
            return True
        # Must be authenticated to create/update
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Anyone can read
        if request.method in permissions.SAFE_METHODS:
            return True
        # Staff can do anything
        if request.user.is_staff:
            return True
        # Allow update/delete only if user is the owner of the object
        if hasattr(obj, 'owner'):
            return obj.owner == request.user
        # For objects without an owner field, allow authenticated users
        return True

