// IrisData.h - Centralized mock data models and store for Iris
#import <UIKit/UIKit.h>

@interface IrisComment : NSObject
@property (nonatomic, copy) NSString *commentId;
@property (nonatomic, copy) NSString *username;
@property (nonatomic, copy) NSString *avatar;
@property (nonatomic, copy) NSString *text;
@property (nonatomic, copy) NSString *timestamp;
@property (nonatomic, assign) NSInteger likes;
@property (nonatomic, assign) BOOL isLiked;
@end

@interface IrisPost : NSObject
@property (nonatomic, copy) NSString *postId;
@property (nonatomic, copy) NSString *username;
@property (nonatomic, copy) NSString *displayName;
@property (nonatomic, copy) NSString *avatar;
@property (nonatomic, copy) NSString *imageKey;
@property (nonatomic, copy) NSString *caption;
@property (nonatomic, copy) NSString *hashtags;
@property (nonatomic, copy) NSString *location;
@property (nonatomic, assign) NSInteger likes;
@property (nonatomic, assign) NSInteger commentsCount;
@property (nonatomic, copy) NSString *timestamp;
@property (nonatomic, assign) BOOL isLiked;
@property (nonatomic, assign) BOOL isBookmarked;
@property (nonatomic, strong) NSMutableArray<IrisComment *> *comments;
@property (nonatomic, assign) CGFloat aspectRatio; // width / height
@property (nonatomic, assign) BOOL isVideo;
@end

@interface IrisStory : NSObject
@property (nonatomic, copy) NSString *storyId;
@property (nonatomic, copy) NSString *username;
@property (nonatomic, copy) NSString *avatar;
@property (nonatomic, copy) NSString *imageKey;
@property (nonatomic, copy) NSString *timestamp;
@property (nonatomic, assign) BOOL viewed;
@property (nonatomic, assign) BOOL isYourStory;
@end

@interface IrisProfile : NSObject
@property (nonatomic, copy) NSString *username;
@property (nonatomic, copy) NSString *displayName;
@property (nonatomic, copy) NSString *avatar;
@property (nonatomic, copy) NSString *bio;
@property (nonatomic, copy) NSString *website;
@property (nonatomic, assign) NSInteger postsCount;
@property (nonatomic, assign) NSInteger followersCount;
@property (nonatomic, assign) NSInteger followingCount;
@property (nonatomic, assign) BOOL isFollowing;
@property (nonatomic, strong) NSArray<NSString *> *postImages;
@end

@interface IrisNotification : NSObject
@property (nonatomic, copy) NSString *notificationId;
@property (nonatomic, copy) NSString *username;
@property (nonatomic, copy) NSString *avatar;
@property (nonatomic, copy) NSString *type; // @"like", @"follow", @"comment", @"mention"
@property (nonatomic, copy) NSString *message;
@property (nonatomic, copy) NSString *timestamp;
@property (nonatomic, copy) NSString *thumbnailImageKey;
@property (nonatomic, assign) BOOL isFollowing;
@end

@interface IrisData : NSObject

@property (nonatomic, strong) NSMutableArray<IrisPost *> *posts;
@property (nonatomic, strong) NSMutableArray<IrisStory *> *stories;
@property (nonatomic, strong) NSMutableDictionary<NSString *, IrisProfile *> *profiles;
@property (nonatomic, strong) NSMutableArray<IrisNotification *> *notifications;
@property (nonatomic, strong) IrisProfile *currentUserProfile;

+ (instancetype)sharedData;

// Feed interactions
- (void)toggleLikeForPost:(IrisPost *)post;
- (void)toggleBookmarkForPost:(IrisPost *)post;
- (void)addComment:(NSString *)text toPost:(IrisPost *)post;
- (void)addNewPostWithCaption:(NSString *)caption location:(NSString *)location audience:(NSString *)audience imageKey:(NSString *)imageKey;

// Follow interactions
- (void)toggleFollowForUsername:(NSString *)username;

// Search
- (NSArray<IrisPost *> *)searchPostsWithQuery:(NSString *)query;

// Asset rendering helper (offline safe procedural photographic backgrounds)
+ (UIImage *)imageForKey:(NSString *)key size:(CGSize)size title:(NSString *)title subtitle:(NSString *)subtitle;

@end
