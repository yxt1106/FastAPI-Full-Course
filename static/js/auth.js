let currentUser = null;
let fetchPromise = null;
// T10
export async function getCurrentUser() {
  if (currentUser) {// 如果有cached用户，立即返回
    return currentUser;
  }

  // Return in-progress fetch to prevent duplicate API calls
  if (fetchPromise) {
    //因为页面的多个部分会同时调用getcurrentUser
    //而不要对重复多个请求调用api
    return fetchPromise;
  }

  const token = localStorage.getItem("access_token");
  if (!token) {
    return null;
  }

  //用fetch而不用解码是因为：
  //只能得到 token 里存的内容，不能直接得到完整的用户资料
  fetchPromise = (async () => {
    try {
      const response = await fetch("/api/users/me", {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (response.ok) {
        currentUser = await response.json();
        return currentUser;
      }
      //如果token不可用或者过期则清除
      localStorage.removeItem("access_token");
      return null;
    } catch (error) {
      console.error("Error fetching current user:", error);
      return null;
    } finally {
      fetchPromise = null;
    }
  })();

  return fetchPromise;
}

export function logout() {
  //退出登录逻辑: 清理token并返回首页
  localStorage.removeItem("access_token");
  currentUser = null;
  window.location.href = "/";
}

export function getToken() {
  return localStorage.getItem("access_token");
}

export function setToken(token) {
  localStorage.setItem("access_token", token);
}

export function clearUserCache() {
  currentUser = null;
}
